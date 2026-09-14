"""Environment loading uses dummy credentials and never invokes the provider."""

import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from meridian.environment import load_environment


class EnvironmentTests(unittest.TestCase):
    def test_dotenv_loads_without_overriding_exports(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            (root / '.env').write_text('OPENAI_API_KEY="dummy-file-key"\nMERIDIAN_TEST_VALUE=from-file\n')
            load_environment(root)
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'dummy-file-key')
            self.assertEqual(os.environ['MERIDIAN_TEST_VALUE'], 'from-file')
            for exported in ('dummy-exported-key', ''):
                os.environ['OPENAI_API_KEY'] = exported
                load_environment(root)
                self.assertEqual(os.environ['OPENAI_API_KEY'], exported)

    def test_missing_file_does_not_search_parent(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            parent = Path(tmp)
            (parent / '.env').write_text('OPENAI_API_KEY=dummy-parent-key\n')
            project = parent / 'project'
            project.mkdir()
            load_environment(project)
            self.assertNotIn('OPENAI_API_KEY', os.environ)

    def test_api_commands_load_selected_root_before_execution(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.env').write_text('OPENAI_API_KEY=dummy-cli-key\n')
            for name, target, extra in (
                ('triage', 'triage', ['--description', 'Example', '--industry', 'retail',
                                      '--company-size', 'small', '--urgency', 'normal']),
                ('evaluate', 'evaluate', []), ('render_cases', 'render', []),
            ):
                module = importlib.import_module(f'meridian.{name}')
                def executed(*args, **kwargs):
                    self.assertEqual(os.environ.get('OPENAI_API_KEY'), 'dummy-cli-key')
                    return Mock(model_dump_json=lambda **kwargs: '{}')
                with self.subTest(command=name), patch.dict(os.environ, {}, clear=True), \
                        patch('sys.argv', [name, '--root', str(root), *extra]), \
                        patch.object(module, target, side_effect=executed) as run, \
                        patch.object(module, 'load_config'), patch('builtins.print'):
                    module.main()
                    run.assert_called_once()

    def test_workbench_loads_before_app_configuration(self):
        from meridian.workbench import create_app
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp)
            (root / '.env').write_text('OPENAI_API_KEY=dummy-server-key\n')
            def configured(project):
                self.assertEqual(project, root)
                self.assertEqual(os.environ.get('OPENAI_API_KEY'), 'dummy-server-key')
                raise RuntimeError('stop before reading application data')
            with patch('meridian.workbench.load_config', side_effect=configured):
                with self.assertRaisesRegex(RuntimeError, 'stop before reading'):
                    create_app(root)

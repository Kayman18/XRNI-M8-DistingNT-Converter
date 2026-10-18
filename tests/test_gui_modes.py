import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import xrni_to_m8 as conv
import test_xrni_normalize as fixtures


@unittest.skipUnless(os.environ.get('DISPLAY') or os.name == 'nt', 'requires a display (use xvfb-run on Linux)')
class GuiTests(unittest.TestCase):
    def setUp(self):
        import xrni_to_m8_gui as gui
        self.gui = gui
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        with patch.object(gui.App, '_app_base_dir', return_value=str(self.base)):
            self.app = gui.App()
        self.app.withdraw()
        self.addCleanup(self.app.destroy)
        patcher = patch.object(gui.App, '_app_base_dir', return_value=str(self.base))
        patcher.start()
        self.addCleanup(patcher.stop)
        fixture = fixtures.NormalizeTests()
        fixture.source = self.base / 'input.xrni'
        fixture.make_archive()
        self.source = fixture.source
        self.app.xrni.set(str(self.source))
        self.app.layer.set(1)
        self.app.inspect(str(self.source))

    def test_three_modes_and_controls(self):
        app = self.app
        for mode, folder, ext in [('xrni', 'XRNI', '.xrni'), ('disting', 'Disting NT', '.json'), ('m8', 'M8', '.wav')]:
            app.output_mode.set(mode)
            app.output_mode_changed()
            self.assertEqual(Path(app.output.get()).parent, self.base / 'Converted' / folder)
            self.assertTrue(app.output.get().endswith(ext))
            for button in app.layer_buttons:
                self.assertEqual(button.instate(['disabled']), mode != 'm8')
            check = app.norm_widget.winfo_children()[0]
            self.assertEqual(check.instate(['disabled']), mode != 'm8')
        # Custom XRNI filenames are always placed in the dedicated output folder.
        out = app._xrni_output_name(requested_path='/elsewhere/custom.xrni')
        self.assertEqual(Path(out), self.base / 'Converted' / 'XRNI' / 'custom.xrni')

    def test_xrni_start_routes_and_completes(self):
        app = self.app
        app.output_mode.set('xrni')
        app.output_mode_changed()
        with patch.object(self.gui.threading, 'Thread') as thread:
            app.start()
            kwargs = thread.call_args.kwargs
            self.assertEqual(kwargs['target'], app.convert_xrni)
            self.assertEqual(kwargs['args'][0], str(self.source))
        # Run the actual worker with main-thread callbacks synchronously.
        with patch.object(app, 'after', side_effect=lambda delay, callback, *args: callback(*args)), \
             patch.object(self.gui.messagebox, 'showinfo') as done, \
             patch.object(self.gui.messagebox, 'showerror') as failed:
            app.convert_xrni(*kwargs['args'])
            failed.assert_not_called()
            done.assert_called_once()
        self.assertTrue(Path(app.output.get()).is_file())
        self.assertFalse(app.go.instate(['disabled']))

    def test_existing_export_workers_still_work(self):
        app = self.app
        with patch.object(app, 'after', side_effect=lambda delay, callback, *args: callback(*args)), \
             patch.object(self.gui.messagebox, 'showinfo'), \
             patch.object(self.gui.messagebox, 'showerror') as failed:
            m8 = self.base / 'Converted' / 'M8' / 'test.wav'
            app.convert(str(self.source), str(m8), 1, False, True)
            self.assertTrue(m8.exists())
            nt = self.base / 'Converted' / 'Disting NT' / 'test.json'
            app.convert_disting(str(self.source), str(nt))
            self.assertTrue(nt.exists())
            failed.assert_not_called()


if __name__ == '__main__':
    unittest.main()

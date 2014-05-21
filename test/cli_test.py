import os
import shutil
from unittest import TestCase

import beets.ui
import beets.library

from helper import TestHelper, captureLog, \
    captureStdout, controlStdin, MockChecker
from beetsplug import check


class CheckTest(TestHelper, TestCase):

    def setUp(self):
        super(CheckTest, self).setUp()
        self.setupBeets()

    def tearDown(self):
        super(CheckTest, self).tearDown()

    def test_add_checksums(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        del item['checksum']
        item.store()

        beets.ui._raw_main(['check', '-a'])

        item.load()
        self.assertIn('checksum', item)

    def test_dont_add_existing_checksums(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        check.set_checksum(item)
        orig_checksum = item['checksum']

        self.modifyFile(item.path)
        beets.ui._raw_main(['check', '-a'])

        item.load()
        self.assertEqual(item['checksum'], orig_checksum)

    def test_add_shows_integrity_warning(self):
        MockChecker.install()
        item = self.addIntegrityFailFixture(checksum=False)

        with captureLog() as logs:
            beets.ui._raw_main(['check', '-a'])

        self.assertIn('WARNING file is corrupt: {}'.format(item.path),
                      '\n'.join(logs))

    def test_check_success(self):
        self.setupFixtureLibrary()
        with captureStdout() as stdout:
            beets.ui._raw_main(['check'])
        self.assertEqual('All checksums successfully verified',
                         stdout.getvalue().split('\n')[-2])

    def test_check_failed_error_log(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        self.modifyFile(item.path)

        try:
            with captureLog('beets.check') as logs:
                beets.ui._raw_main(['check'])
        except SystemExit:
            pass

        self.assertIn('FAILED: {}'.format(item.path), '\n'.join(logs))

    def test_not_found_error(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        item.path = '/doesnotexist'
        item.store()

        try:
            with captureLog('beets.check') as logs:
                beets.ui._raw_main(['check'])
        except SystemExit:
            pass

        self.assertIn("ERROR [Errno 2] No such file or directory: '{}'"
                      .format(item.path), '\n'.join(logs))

    def test_check_failed_exit_code(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        self.modifyFile(item.path)

        with self.assertRaises(SystemExit) as exit:
            beets.ui._raw_main(['check'])
        self.assertEqual(exit.exception.code, 15)

    def test_check_without_integrity_config(self):
        self.config['check']['integrity'] = False
        MockChecker.install()
        self.addIntegrityFailFixture()

        with captureLog() as logs:
            beets.ui._raw_main(['check'])

        self.assertNotIn('WARNING file is corrupt', '\n'.join(logs))

    def test_check_only_integrity(self):
        MockChecker.install()
        self.addIntegrityFailFixture(checksum=False)
        self.addCorruptedFixture()

        with captureLog() as logs:
            beets.ui._raw_main(['check', '-i'])

        self.assertIn('WARNING file is corrupt', '\n'.join(logs))
        self.assertNotIn('FAILED', '\n'.join(logs))

    def test_force_all_update(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item['checksum']
        self.modifyFile(item.path)

        beets.ui._raw_main(['check', '--force', '--update'])

        item.load()
        self.assertNotEqual(item['checksum'], orig_checksum)
        check.verify(item)

    def test_update_all_confirmation(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item['checksum']
        self.modifyFile(item.path)

        with captureStdout() as stdout, controlStdin(u'y'):
            beets.ui._raw_main(['check', '--update'])

        self.assertIn('Do you want to overwrite all checksums',
                      stdout.getvalue())

        item.load()
        self.assertNotEqual(item['checksum'], orig_checksum)
        check.verify(item)

    def test_update_all_confirmation_no(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item['checksum']
        self.modifyFile(item.path)

        with controlStdin(u'n'):
            beets.ui._raw_main(['check', '--update'])

        item.load()
        self.assertEqual(item['checksum'], orig_checksum)

    def test_export(self):
        self.setupFixtureLibrary()
        with captureStdout() as stdout:
            beets.ui._raw_main(['check', '--export'])

        item = self.lib.items().get()
        self.assertIn('{} *{}\n'.format(item.checksum, item.path),
                      stdout.getvalue())


class IntegrityCheckTest(TestHelper, TestCase):

    def setUp(self):
        super(IntegrityCheckTest, self).setUp()
        self.setupBeets()
        self.setupFixtureLibrary()
        self.enableIntegrityCheckers()

    def tearDown(self):
        super(IntegrityCheckTest, self).tearDown()

    def test_mp3_integrity(self):
        item = self.lib.items(['path::truncated.mp3']).get()

        with captureLog() as logs:
            beets.ui._raw_main(['check'])
        self.assertIn('WARNING It seems that file is '
                      'truncated or there is garbage at the '
                      'end of the file: {}'.format(item.path), logs)

    def test_flac_integrity(self):
        item = self.lib.items('truncated.flac').get()

        with captureLog() as logs:
            beets.ui._raw_main(['check'])
        self.assertIn(
            'WARNING while decoding data: {}'.format(item.path), logs)

    def test_ogg_vorbis_integrity(self):
        item = self.lib.items('truncated.ogg').get()

        with captureLog() as logs:
            beets.ui._raw_main(['check'])
        self.assertIn('WARNING serialno 1038587646 missing *** eos: {}'
                      .format(item.path), logs)


class ToolListTest(TestHelper, TestCase):

    def setUp(self):
        super(ToolListTest, self).setUp()
        self.enableIntegrityCheckers()
        self.setupBeets()
        self.orig_path = os.environ['PATH']
        os.environ['PATH'] = self.temp_dir

    def tearDown(self):
        super(ToolListTest, self).tearDown()
        os.environ['PATH'] = self.orig_path

    def test_list(self):
        with captureStdout() as stdout:
            beets.ui._raw_main(['check', '--list-tools'])
        self.assertIn('mp3val', stdout.getvalue())
        self.assertIn('flac', stdout.getvalue())
        self.assertIn('oggz-validate', stdout.getvalue())

    def test_found_mp3val(self):
        shutil.copy('/bin/echo', os.path.join(self.temp_dir, 'mp3val'))
        with captureStdout() as stdout:
            beets.ui._raw_main(['check', '--list-tools'])
        self.assertRegexpMatches(stdout.getvalue(), r'mp3val *found')

    def test_oggz_validate_not_found(self):
        with captureStdout() as stdout:
            beets.ui._raw_main(['check', '--list-tools'])
        self.assertRegexpMatches(stdout.getvalue(),
                                 r'oggz-validate *not found')

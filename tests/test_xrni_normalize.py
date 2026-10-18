import io
import os
from pathlib import Path
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import soundfile as sf
import xrni_to_m8 as conv


def wav_bytes(audio, subtype='PCM_16', rate=48000):
    buf = io.BytesIO()
    sf.write(buf, audio, rate, format='WAV', subtype=subtype)
    return buf.getvalue()


def instrument_xml():
    root = ET.Element('RenoiseInstrument', doc_version='13')
    ET.SubElement(root, 'Name').text = 'Layered instrument & loops'
    samples = ET.SubElement(root, 'Samples')
    for index, (start, end) in enumerate(((0, 63), (64, 127))):
        sample = ET.SubElement(samples, 'Sample')
        for key, value in {'Name': f'Original name {index}', 'LoopMode': 'Forward',
                           'LoopStart': 1, 'LoopEnd': 3, 'Volume': 0.7,
                           'Transpose': -12, 'FineTune': 4}.items():
            ET.SubElement(sample, key).text = str(value)
        mapping = ET.SubElement(sample, 'Mapping')
        for key, value in {'Layer': 'Note-On Layer', 'BaseNote': 48,
                           'NoteStart': 24, 'NoteEnd': 71,
                           'VelocityStart': start, 'VelocityEnd': end}.items():
            ET.SubElement(mapping, key).text = str(value)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.xrni'
        self.output = self.root / 'Converted' / 'XRNI' / 'normalized.xrni'

    def make_archive(self, wav=None):
        wav = wav if wav is not None else wav_bytes([0.1, -0.25, 0.125, 0.0])
        with zipfile.ZipFile(self.source, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.comment = b'original archive comment'
            z.writestr('Instrument.xml', instrument_xml())
            info = zipfile.ZipInfo('SampleData/Sample00 first.WAV', (2020, 1, 2, 3, 4, 6))
            info.comment = b'sample comment'
            info.external_attr = 0o644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, wav)
            z.writestr('SampleData/Sample01 silent.wav', wav_bytes(np.zeros((4, 2)), 'PCM_24'))
            z.writestr('SampleData/', b'')
            flac = io.BytesIO()
            sf.write(flac, [0.1, -0.2], 32000, format='FLAC')
            z.writestr('SampleData/Sample02 untouched.flac', flac.getvalue())
            z.writestr('Other/settings.bin', b'\x00\xffuntouched')

    def test_archive_metadata_and_mappings_reopen(self):
        self.make_archive()
        original = self.source.read_bytes()
        result = conv.write_normalized_xrni(self.source, self.output)
        self.assertEqual(result['wav_count'], 2)
        self.assertEqual(self.source.read_bytes(), original)
        with zipfile.ZipFile(self.source) as src, zipfile.ZipFile(self.output) as dst:
            self.assertIsNone(dst.testzip())
            self.assertEqual(src.namelist(), dst.namelist())
            self.assertEqual(src.comment, dst.comment)
            for a, b in zip(src.infolist(), dst.infolist()):
                for field in ('date_time', 'comment', 'external_attr', 'extra', 'compress_type'):
                    self.assertEqual(getattr(a, field), getattr(b, field))
                if a.filename != 'SampleData/Sample00 first.WAV':
                    self.assertEqual(src.read(a), dst.read(b))
            self.assertEqual(src.read('Instrument.xml'), dst.read('Instrument.xml'))
            samples = ET.fromstring(dst.read('Instrument.xml')).findall('.//Samples/Sample')
            self.assertEqual([s.findtext('Mapping/VelocityStart') for s in samples], ['0', '64'])
            self.assertEqual([s.findtext('LoopEnd') for s in samples], ['3', '3'])
        a, before = conv.parse_all_xrni(self.source)
        b, after = conv.parse_all_xrni(self.output)
        try:
            self.assertEqual(before, after)
            self.assertEqual(len(after), 2)
            for item in after:
                audio, rate = conv.decode(b, item)
                self.assertEqual(len(audio), 4)
                self.assertEqual(rate, 48000)
        finally:
            a.close(); b.close()

    def test_formats_rates_channels_and_shared_gain(self):
        for subtype, bits in [('PCM_U8', 8), ('PCM_16', 16), ('PCM_24', 24),
                              ('PCM_32', 32), ('FLOAT', None), ('DOUBLE', None)]:
            for channels, rate in [(1, 22050), (2, 96000)]:
                with self.subTest(subtype=subtype, channels=channels):
                    audio = np.array([[0.25, 0.125], [-0.125, -0.0625], [0, 0]])[:, :channels]
                    data = wav_bytes(audio, subtype, rate)
                    out = conv.normalize_wav_bytes(data)
                    info = sf.info(io.BytesIO(out))
                    self.assertEqual((info.subtype, info.channels, info.samplerate, info.frames),
                                     (subtype, channels, rate, 3))
                    normalized, _ = sf.read(io.BytesIO(out), always_2d=True, dtype='float64')
                    target = 1 - 2 ** (1 - bits) if bits else 1
                    self.assertAlmostEqual(np.max(np.abs(normalized)), target, places=7)
                    np.testing.assert_allclose(normalized, audio / 0.25 * target,
                                               atol=2 ** (1 - bits) if bits else 1e-7)

    def test_silence_and_empty_unchanged(self):
        for audio in (np.zeros((20, 2)), np.zeros((0, 1))):
            original = wav_bytes(audio)
            self.assertEqual(conv.normalize_wav_bytes(original), original)

    def test_embedded_chunks_preserved(self):
        data = wav_bytes([0.1, -0.2])
        extra = conv.chunk(b'smpl', bytes(range(60))) + conv.chunk(b'LIST', b'INFOoriginal name')
        data = data[:4] + struct.pack('<I', len(data) - 8 + len(extra)) + data[8:] + extra
        out = conv.normalize_wav_bytes(data)
        start, end = conv._wav_data_span(data)
        self.assertEqual(out[:start], data[:start])
        self.assertEqual(out[end:], data[end:])

    def test_wavex_preserves_extensible_header(self):
        buf = io.BytesIO()
        sf.write(buf, np.full((8, 2), 0.25), 48000, format='WAVEX', subtype='PCM_24')
        original = buf.getvalue()
        out = conv.normalize_wav_bytes(original)
        start, end = conv._wav_data_span(original)
        self.assertEqual(out[:start], original[:start])
        self.assertEqual(out[end:], original[end:])
        self.assertEqual(sf.info(io.BytesIO(out)).subtype, 'PCM_24')

    def test_refuses_overwrite_and_source_alias(self):
        self.make_archive()
        original = self.source.read_bytes()
        with self.assertRaises(FileExistsError):
            conv.write_normalized_xrni(self.source, self.source)
        alias = self.root / 'alias.xrni'
        os.link(self.source, alias)
        with self.assertRaises(FileExistsError):
            conv.write_normalized_xrni(self.source, alias)
        conv.write_normalized_xrni(self.source, self.output)
        converted = self.output.read_bytes()
        with self.assertRaises(FileExistsError):
            conv.write_normalized_xrni(self.source, self.output)
        self.assertEqual(self.output.read_bytes(), converted)
        self.assertEqual(self.source.read_bytes(), original)

    def test_failure_does_not_publish_partial_archive(self):
        for bad in (b'not a wav', wav_bytes([float('nan')], 'FLOAT'),
                    wav_bytes([0.25], 'ULAW')):
            with self.subTest(bad=bad[:12]):
                self.make_archive(bad)
                with self.assertRaises(ValueError):
                    conv.write_normalized_xrni(self.source, self.output)
                self.assertFalse(self.output.exists())
                self.assertEqual(list(self.output.parent.iterdir()), [])

    def test_missing_or_invalid_xml(self):
        for name, data in [('other.txt', b'no xml'), ('Instrument.xml', b'<broken')]:
            with zipfile.ZipFile(self.source, 'w') as z:
                z.writestr(name, data)
            with self.assertRaises((ValueError, ET.ParseError)):
                conv.write_normalized_xrni(self.source, self.output)
            self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()

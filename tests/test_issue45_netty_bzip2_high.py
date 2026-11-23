"""Source identity, artifact and CLI controls for the bounded Bzip2 review."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import inspect_issue45_netty_bzip2_high as bzip2


def make_jar(entries):
    buf = BytesIO()
    with ZipFile(buf, 'w', ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return buf.getvalue()


def identity(raw):
    return {'size_bytes': len(raw), 'sha1': hashlib.sha1(raw).hexdigest(),
            'sha256': hashlib.sha256(raw).hexdigest()}


class Bzip2EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (cls.ledger, cls.v3, cls.target, cls.reviewed, cls.games,
         cls.prior, cls.mod) = bzip2.context()
        cls.critical = bzip2.sni.load_inputs()[2]
        cls.records = {path: (ROOT / path).read_bytes() for path in
                       (bzip2.CLIENTS, bzip2.CODECS, bzip2.FABRIC, bzip2.PRODUCT, bzip2.PIPELINE)}
        (cls.clients, cls.codecs, cls.fabric, cls.product, cls.pipeline) = (
            json.loads(cls.records[path]) for path in
            (bzip2.CLIENTS, bzip2.CODECS, bzip2.FABRIC, bzip2.PRODUCT, bzip2.PIPELINE))

    def validate(self, clients=None, codecs=None, fabric=None, product=None, pipeline=None):
        bzip2.validate_inputs(self.games, self.clients if clients is None else clients,
            self.codecs if codecs is None else codecs, self.fabric if fabric is None else fabric,
            self.product if product is None else product, self.pipeline if pipeline is None else pipeline)

    def test_review_and_register_bind_every_occurrence_and_remain_blocking(self):
        self.validate()
        review = bzip2.make_review(self.ledger, self.target, self.reviewed, self.games,
                                   self.codecs, self.records, self.mod)
        raw = (ROOT / bzip2.REVIEW).read_bytes()
        self.assertEqual(json.loads(raw), review)
        self.assertEqual((review['occurrence_count'], review['source_group_count'],
                          review['minecraft_version_count']), (13, 10, 28))
        occurrences = review['occurrences']
        self.assertEqual(len({(o['source_kind'], o['group'], o['source_sha'], o['purl'])
                              for o in occurrences}), 13)
        for occurrence in occurrences:
            self.assertTrue(occurrence['release_blocking'])
            self.assertFalse(occurrence['risk_accepted'])
            self.assertRegex(occurrence['source_report_archive_sha256'], r'^[a-f0-9]{64}$')
            self.assertRegex(occurrence['product_jar_sha256'], r'^[a-f0-9]{64}$')
            self.assertTrue(all(len(a['version_metadata_sha256']) == 64
                                for a in occurrence['minecraft_artifacts']))
        register_raw = (ROOT / bzip2.CURRENT).read_bytes()
        register = json.loads(register_raw)
        self.assertEqual(register, bzip2.make_register(self.v3, review, raw))
        self.assertEqual(register['focused_coverage'], {'advisory_ids': 23, 'critical_occurrences': 22,
            'high_occurrences': 108, 'total_occurrences': 130, 'high_occurrences_without_focused_evidence': 69})
        self.assertTrue(all(o['release_blocking'] and not o['risk_accepted']
                            for a in register['advisories'] for o in a['occurrences']))
        self.assertEqual(self.ledger['bzip2_high_focused_priority_register']['sha256'],
                         hashlib.sha256(register_raw).hexdigest())

    def test_source_binding_rejects_same_count_duplicate_and_identity_mutations(self):
        bzip2.bind_target(self.target, self.critical, self.prior, self.mod)
        for mutation in ('duplicate', 'source', 'package', 'scope', 'blocking', 'acceptance'):
            with self.subTest(mutation=mutation):
                target = copy.deepcopy(self.target)
                row = target['occurrences'][0]
                if mutation == 'duplicate':
                    target['occurrences'][0] = copy.deepcopy(target['occurrences'][1])
                elif mutation == 'source':
                    row['source_sha'] = '0' * 40
                elif mutation == 'package':
                    row['purl'] = row['purl'].replace('4.1.77.Final', '4.1.78.Final')
                elif mutation == 'scope':
                    row['scopes'].pop()
                elif mutation == 'blocking':
                    row['release_blocking'] = False
                else:
                    row['risk_accepted'] = True
                with self.assertRaisesRegex(ValueError, 'Bzip2 (source identity|runtime scope)'):
                    bzip2.bind_target(target, self.critical, self.prior, self.mod)

    def test_client_inventory_mutations_are_rejected(self):
        self.validate()
        for mutation in ('missing', 'duplicate', 'metadata_hash', 'client_hash', 'source_url', 'literal'):
            with self.subTest(mutation=mutation):
                clients = copy.deepcopy(self.clients)
                if mutation == 'missing':
                    clients['games'].pop()
                elif mutation == 'duplicate':
                    clients['games'][0] = copy.deepcopy(clients['games'][1])
                elif mutation == 'metadata_hash':
                    clients['games'][0]['manifest_sha256'] = '0' * 64
                elif mutation == 'client_hash':
                    clients['games'][0]['client_sha256'] = '0' * 64
                elif mutation == 'source_url':
                    clients['games'][0]['client_url'] = 'https://example.invalid/client.jar'
                else:
                    clients['games'][0]['literal_hits'] = [{'class_file': 'Caller.class'}]
                reason = 'Bzip2 client (coverage differs|artifact or literal observations differ)'
                with self.assertRaisesRegex(ValueError, reason):
                    self.validate(clients=clients)

    def test_codec_inventory_rejects_missing_duplicate_and_wrong_artifact(self):
        self.validate()
        for mutation in ('missing', 'duplicate', 'jar_hash', 'class_path'):
            with self.subTest(mutation=mutation):
                codecs = copy.deepcopy(self.codecs)
                if mutation == 'missing':
                    codecs['libraries'].pop()
                elif mutation == 'duplicate':
                    codecs['libraries'][0] = copy.deepcopy(codecs['libraries'][1])
                elif mutation == 'jar_hash':
                    codecs['libraries'][0]['sha256'] = '0' * 64
                else:
                    codecs['libraries'][0]['class_file'] = 'wrong.class'
                with self.assertRaisesRegex(ValueError, 'Bzip2 codec (coverage|class identity) differs'):
                    self.validate(codecs=codecs)

    def test_download_checks_real_jar_and_class_bytes(self):
        raw = make_jar([(bzip2.DECODER, b'synthetic decoder class')])
        artifact = identity(raw)
        item = bzip2.inspect_codec(raw, artifact, 'pkg:maven/io.netty/netty-codec@4.1.77.Final',
                                  'https://libraries.minecraft.net/example.jar')
        with patch.object(bzip2.ipfilter, 'download_mojang_library', return_value=raw) as download:
            bzip2.verify_codec_downloads({'libraries': [item]})
            download.assert_called_once_with(item['url'], item['size_bytes'])
            forged = copy.deepcopy(item)
            forged['class_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'downloaded Bzip2 codec class differs'):
                bzip2.verify_codec_downloads({'libraries': [forged]})
            # If the real class-byte comparison is bypassed, the same forged
            # record would be accepted; this proves the mutation is discriminating.
            with patch.object(bzip2, 'inspect_codec', return_value=forged):
                bzip2.verify_codec_downloads({'libraries': [forged]})
        with self.assertRaisesRegex(ValueError, 'Bzip2 codec JAR checksum differs'):
            bzip2.inspect_codec(raw + b'x', artifact, item['purl'], item['url'])
        absent = make_jar([('example/Other.class', b'other')])
        with self.assertRaises(KeyError):
            bzip2.inspect_codec(absent, identity(absent), item['purl'], item['url'])

    def test_client_class_pins_are_checked_against_jar_bytes(self):
        connection = b'setupCompression net/minecraft/network/CompressionDecoder addAfter'
        decoder = b'java/util/zip/Inflater io/netty/handler/codec/ByteToMessageDecoder'
        raw = make_jar([(bzip2.MC_CONNECTION, connection), (bzip2.MC_DECODER, decoder)])
        info = identity(raw)
        row = {'client_size_bytes': info['size_bytes'], 'client_sha1': info['sha1'],
               'client_sha256': info['sha256'], 'class_files_scanned': 2, 'literal_hits': []}
        pipeline = {'connection_sha256': bzip2.sha(connection), 'decoder_sha256': bzip2.sha(decoder)}
        bzip2.verify_client_bytes(raw, row, pipeline)
        bad = dict(pipeline, connection_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'downloaded Minecraft compression classes differ'):
            bzip2.verify_client_bytes(raw, row, bad)
        with self.assertRaisesRegex(ValueError, 'downloaded Minecraft client checksum differs'):
            bzip2.verify_client_bytes(raw + b'x', row, pipeline)

    def test_offline_cli_and_explicit_independent_verification(self):
        out, err = StringIO(), StringIO()
        with patch.object(sys, 'argv', ['bzip2']), \
             patch.object(bzip2, 'build_opener', side_effect=AssertionError('unexpected network')), \
             patch.object(bzip2.ipfilter, 'download_mojang_library', side_effect=AssertionError('unexpected network')), \
             redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(bzip2.main(), 0, err.getvalue())
        with patch.object(sys, 'argv', ['bzip2', '--verify-codec-download', '--verify-client-download',
                                       '--verify-runtime-cache', '--javap', 'synthetic-javap']), \
             patch.object(bzip2, 'verify_codec_downloads') as codec, \
             patch.object(bzip2, 'verify_client_download') as client, \
             patch.object(bzip2, 'verify_runtime_cache') as cache, \
             redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(bzip2.main(), 0)
            codec.assert_called_once_with(self.codecs)
            client.assert_called_once_with(self.clients, self.pipeline, Path('synthetic-javap'))
            self.assertEqual(cache.call_count, 1)
        for flag, name in (('--verify-codec-download', 'verify_codec_downloads'),
                           ('--verify-client-download', 'verify_client_download'),
                           ('--verify-runtime-cache', 'verify_runtime_cache')):
            with self.subTest(flag=flag), patch.object(sys, 'argv', ['bzip2', flag]), \
                 patch.object(bzip2, name, side_effect=ValueError('synthetic verification failure')), \
                 redirect_stdout(StringIO()), redirect_stderr(StringIO()) as stderr:
                self.assertEqual(bzip2.main(), 1)
                self.assertIn('synthetic verification failure', stderr.getvalue())

    def test_invalid_client_download_origin_fails_before_network(self):
        clients = copy.deepcopy(self.clients)
        row = next(x for x in clients['games'] if x['minecraft_version'] == '26.2')
        row['client_url'] = 'https://example.invalid/client.jar'
        with patch.object(bzip2, 'build_opener', side_effect=AssertionError('unexpected network')):
            with self.assertRaisesRegex(ValueError, 'Minecraft client source URL or size differs'):
                bzip2.verify_client_download(clients, self.pipeline, Path('synthetic-javap'))

    def test_downloaded_client_disassembly_is_required_and_compared(self):
        connection = b'setupCompression net/minecraft/network/CompressionDecoder addAfter'
        decoder = b'java/util/zip/Inflater io/netty/handler/codec/ByteToMessageDecoder'
        raw = make_jar([(bzip2.MC_CONNECTION, connection), (bzip2.MC_DECODER, decoder)])
        info = identity(raw)
        url = 'https://piston-data.mojang.com/v1/objects/' + info['sha1'] + '/client.jar'
        row = {'minecraft_version': '26.2', 'client_url': url, 'client_size_bytes': info['size_bytes'],
               'client_sha1': info['sha1'], 'client_sha256': info['sha256'],
               'class_files_scanned': 2, 'literal_hits': []}
        pipeline = {'connection_sha256': bzip2.sha(connection), 'decoder_sha256': bzip2.sha(decoder)}
        javap = Path('synthetic-javap')
        with patch.object(bzip2, 'build_opener') as opener, \
             patch.object(bzip2, 'inspect_pipeline', return_value=pipeline) as disassemble:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.geturl.return_value = url
            response.read.return_value = raw
            bzip2.verify_client_download({'games': [row]}, pipeline, javap)
            disassemble.assert_called_once_with(raw, javap)
            disassemble.return_value = dict(pipeline, connection_sha256='0' * 64)
            with self.assertRaisesRegex(ValueError, 'downloaded Minecraft pipeline disassembly differs'):
                bzip2.verify_client_download({'games': [row]}, pipeline, javap)
        with patch.object(bzip2, 'build_opener', side_effect=AssertionError('unexpected network')):
            with self.assertRaisesRegex(ValueError, 'javap is required'):
                bzip2.verify_client_download({'games': [row]}, pipeline, None)


if __name__ == '__main__':
    unittest.main()

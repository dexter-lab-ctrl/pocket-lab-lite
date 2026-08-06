import assert from 'node:assert/strict';
import test from 'node:test';

import {
  safeSensitiveCandidate,
  sanitizeRuntimeEvidenceText,
} from '../../scripts/test/parity/runtime-evidence-sanitizer.mjs';

test('rejects short and common UI words as identity candidates', () => {
  assert.equal(safeSensitiveCandidate('i'), '');
  assert.equal(safeSensitiveCandidate('device'), '');
  assert.equal(safeSensitiveCandidate('access'), '');
  assert.equal(safeSensitiveCandidate('Review'), '');
  assert.equal(safeSensitiveCandidate('alpha'), '');
  assert.equal(safeSensitiveCandidate('alphax'), 'alphax');
});

test('redacts exact identities without damaging ordinary UI text', () => {
  const input = 'Devices My Devices Review device access for DJ-PC and pocket-lab-lite-server.';
  const output = sanitizeRuntimeEvidenceText(input, [
    'DJ-PC',
    'pocket-lab-lite-server',
    'i',
    'device',
  ]);

  assert.equal(
    output,
    'Devices My Devices Review device access for [private-identity] and [private-identity].',
  );
});

test('uses token boundaries for alphanumeric identities', () => {
  const output = sanitizeRuntimeEvidenceText(
    'Node alphax is online; alphaxbeta remains ordinary text.',
    ['alphax'],
  );
  assert.equal(
    output,
    'Node [private-identity] is online; alphaxbeta remains ordinary text.',
  );
});

test('does not recursively redact existing markers', () => {
  const value = 'Device [private-identity] is ready.';
  assert.equal(
    sanitizeRuntimeEvidenceText(value, ['private', 'identity']),
    value,
  );
});

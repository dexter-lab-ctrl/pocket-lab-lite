import React from 'react';
import RecoveryConfirmSheetLazy from './RecoveryConfirmSheetLazy.jsx';

export default { title: 'Pocket Lab Lite/Recovery/Protected Confirmation', component: RecoveryConfirmSheetLazy, tags:['autodocs'] };
const backup = { backup_id: 'fixture-backup-2026', created_at:'2026-10-10T10:00:00Z', verification_status:'verified', size_bytes:10240 };
const preview = { preview_id:'fixture-preview', backup_id:backup.backup_id, status:'ready', change_count:3,
  included_components:['Pocket Lab settings', 'safe app metadata'], excluded_components:['Photos and media'] };
const noop = () => {};
export const RestoreImpact = {args:{ kind:'lite', backup,preview,location:{display_name:'Selected backup location',available:true},onCancel:noop,onConfirm:noop }};
export const MissingImpact = {args:{ kind:'lite',backup,preview:{preview_id:'fixture-preview',backup_id:backup.backup_id,status:'ready'},onCancel:noop,onConfirm:noop }};
export const GuardedDatabase = {args:{ kind:'database',backup,preview,onCancel:noop,onConfirm:noop }};
export const BusyNoDoubleSubmit = {args:{ kind:'lite',backup,preview,busy:true,onCancel:noop,onConfirm:noop }};

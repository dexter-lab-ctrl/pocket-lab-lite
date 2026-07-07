import { createPortal } from 'react-dom';

export default function AppManagePortal({ open, children }) {
  if (!open || typeof document === 'undefined' || !document.body) return null;
  return createPortal(children, document.body);
}

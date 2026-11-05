import { useEffect, useState } from 'react';

// Media-query adaptation only. Sheet sizing and gestures belong to shared LiteSheet/useMobileSheetSnap.
export function useRecoveryMobileSheet() {
  const [mobile, setMobile] = useState(() => typeof window !== 'undefined' && window.matchMedia?.('(max-width: 700px)').matches === true);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const query = window.matchMedia('(max-width: 700px)');
    const update = () => setMobile(query.matches);
    update();
    query.addEventListener?.('change', update);
    return () => query.removeEventListener?.('change', update);
  }, []);
  return mobile;
}

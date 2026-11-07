import React, { useEffect, useId, useRef } from 'react';
import { ArrowLeft, ChevronRight } from 'lucide-react';

/**
 * Home-only composition of the existing LiteDetailsPanel portal and scroll owner.
 * Navigation mirrors the grouped native settings pattern from PR #637; the
 * presentation switches at the *panel container*, not the browser viewport.
 * No backend state or navigation authority is retained here.
 */
export default function HomeGroupedSections({
  groups, section, onSectionChange, defaultSection, navigation,
  title, children,
}) {
  const selected = section || defaultSection;
  const items = groups.flatMap((group) => group.items);
  const activeItem = items.find((item) => item.id === selected) || items[0];
  const detailTitleRef = useRef(null);
  const detailRegionId = useId();
  const lastSelectedId = useRef(null);
  const returnToIndexRef = useRef(false);
  const enteredSectionRef = useRef(false);

  useEffect(() => {
    if (enteredSectionRef.current && section) {
      detailTitleRef.current?.focus({ preventScroll: true });
      enteredSectionRef.current = false;
    }
    if (returnToIndexRef.current && !section) {
      const rows = Array.from(navigation?.navRef?.current?.querySelectorAll('[data-home-section-id]') || []);
      (rows.find((row) => row.dataset.homeSectionId === lastSelectedId.current) || rows[0])
        ?.focus({ preventScroll: true });
      returnToIndexRef.current = false;
    }
  }, [section, navigation]);

  function selectSection(id) {
    lastSelectedId.current = id;
    enteredSectionRef.current = true;
    navigation?.reveal?.(true);
    onSectionChange(id);
  }

  function backToIndex() {
    returnToIndexRef.current = true;
    navigation?.reveal?.(true);
    onSectionChange(null);
  }

  return (
    <div className="lite-home-settings-workspace" data-home-settings-view={section ? 'section' : 'index'}
      data-home-settings-selected={selected}>
      <div className="lite-home-settings-index">
        <nav ref={navigation?.navRef} aria-label={title + ' sections'} className="lite-home-settings-navigation">
          {groups.map((group) => (
            <div className="lite-home-settings-group" key={group.label}>
              <h2>{group.label}</h2>
              <div className="lite-home-settings-rows">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <button key={item.id} type="button" className="lite-home-settings-row"
                      aria-label={item.label} data-home-section-id={item.id} aria-controls={detailRegionId}
                      aria-current={selected === item.id ? 'page' : undefined}
                      onClick={() => selectSection(item.id)}>
                      <Icon size={19} aria-hidden="true" />
                      <span><strong>{item.label}</strong><small>{item.description}</small></span>
                      <ChevronRight size={17} aria-hidden="true" className="lite-home-settings-chevron" />
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>
      <div id={detailRegionId} className="lite-home-settings-detail" role="region" aria-label={activeItem?.label || title}>
        <button type="button" className="lite-home-settings-back" onClick={backToIndex}>
          <ArrowLeft size={17} aria-hidden="true" /> All {title.toLowerCase()} sections
        </button>
        <header className="lite-home-settings-detail-heading">
          <h2 ref={detailTitleRef} tabIndex={-1}>{activeItem?.label}</h2>
          <p>{activeItem?.description}</p>
        </header>
        <div className="lite-home-settings-section-content">{children}</div>
      </div>
    </div>
  );
}

(() => {
  const labelProgressBars = (root = document) => {
    const label = (element) => {
      if (element?.matches?.('.md-progress[role="progressbar"]') && !element.hasAttribute('aria-label')) {
        element.setAttribute('aria-label', 'Page loading progress');
      }
    };

    label(root);
    root?.querySelectorAll?.('.md-progress[role="progressbar"]').forEach(label);
  };

  const enhanceAccessibility = () => {
    labelProgressBars();
    const searchDialog = document.querySelector('[data-md-component="search"][role="dialog"]');
    if (searchDialog && !searchDialog.hasAttribute('aria-label')) {
      searchDialog.setAttribute('aria-label', 'Search documentation');
    }

    document.querySelectorAll('.md-content a[href^="http"]').forEach((link) => {
      try {
        if (new URL(link.href).origin !== window.location.origin) {
          link.rel = 'noopener noreferrer';
          link.dataset.external = 'true';
        }
      } catch (_) {
        // Strict MkDocs validation owns malformed authored links.
      }
    });
  };

  const canPrefetch = () => {
    const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (connection?.saveData) return false;
    return !['slow-2g', '2g'].includes(connection?.effectiveType);
  };

  const prefetched = new Set();
  const prefetch = (anchor) => {
    if (!canPrefetch() || !anchor?.href) return;
    const url = new URL(anchor.href, window.location.href);
    if (url.origin !== window.location.origin || prefetched.has(url.href)) return;
    prefetched.add(url.href);
    const hint = document.createElement('link');
    hint.rel = 'prefetch';
    hint.href = url.href;
    hint.as = 'document';
    document.head.appendChild(hint);
  };

  const enhanceIntentNavigation = () => {
    document.querySelectorAll('a.pl-intent-link').forEach((anchor) => {
      if (anchor.dataset.plIntentBound === 'true') return;
      anchor.dataset.plIntentBound = 'true';
      anchor.addEventListener('pointerenter', () => prefetch(anchor), { once: true, passive: true });
      anchor.addEventListener('focus', () => prefetch(anchor), { once: true });
      anchor.addEventListener('touchstart', () => prefetch(anchor), { once: true, passive: true });
    });
  };

  const enhanceScrollableTables = () => document.querySelectorAll('.md-typeset__scrollwrap,.md-typeset__table,.pl-architecture-table,.pl-kg-domain-table').forEach((region) => {
    const update = () => {
      const scrollable = region.scrollWidth > region.clientWidth + 1;
      region.dataset.plScrollable = scrollable;
      if (scrollable) {
        region.tabIndex = 0;
        region.setAttribute('role', 'region');
        region.setAttribute('aria-label', 'Scrollable table');
      }
    };
    if (!region.dataset.plScrollBound) {
      region.dataset.plScrollBound = 'true';
      region.addEventListener('scroll', update, { passive: true });
      region.addEventListener('keydown', (event) => {
        const key = event.key;
        if (!/^(ArrowLeft|ArrowRight)$/.test(key)) return;
        region.scrollBy({ left: (key === 'ArrowLeft' ? -1 : 1) * Math.max(48, region.clientWidth * .7), behavior: 'smooth' });
        event.preventDefault();
      });
    }
    update();
  });

  let progressObserver;
  const observeProgressBars = () => {
    if (progressObserver || !document.body) return;
    progressObserver = new MutationObserver((records) => {
      for (const record of records) {
        for (const node of record.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) labelProgressBars(node);
        }
      }
    });
    progressObserver.observe(document.body, { childList: true, subtree: true });
  };

  const enhanceKnowledgeGraph = () => {
const root=document.querySelector('[data-pl-knowledge-graph="true"]');
if(!root||root.dataset.plKgBound==='true')return;
root.dataset.plKgBound='true';
const q=s=>root.querySelector(s);
const [search,type,domain,relType,confidence]=[
'[data-kg-search]','[data-kg-type]','[data-kg-domain]',
'[data-kg-relation]','[data-kg-confidence]'
].map(q);
const results=q('.pl-kg-results');
const inspector=q('[data-kg-inspector]');
const el=(tag,cls='',text)=>{
const n=document.createElement(tag);
if(cls)n.className=cls;
if(text!=null)n.textContent=String(text);
return n;
};
const add=(p,...nodes)=>(p.append(...nodes),p);
const fail=message=>{
results.replaceChildren(add(el('div','pl-empty-state'),
el('strong','','Knowledge Graph explorer unavailable'),
el('p','',message),
el('code','','contracts/generated/knowledge/index.json')));
inspector.replaceChildren(
el('span','pl-card-kicker','Entity inspector'),
el('strong','','Static graph remains authoritative'),
el('p','','Use the canonical export while the browser projection is unavailable.')
);
};
const prefix=location.pathname.includes('/generated/')
?location.pathname.split('/generated/')[0]:'';
fetch(
`${prefix}/generated/assets/knowledge/knowledge-graph-explorer.json`,
{ credentials: 'same-origin' }
)
.then(r=>{
if(!r.ok)throw new Error(`HTTP ${r.status}`);
return r.json();
})
.then(payload=>{
if(
!payload||
!Array.isArray(payload.entities)||
!Array.isArray(payload.relations)
)throw new Error(
'generated explorer payload has an invalid shape'
);

if(
payload.max_hops !== 1||
payload.live_runtime !== false
)throw new Error(
'generated explorer payload violated its one-hop/static boundary'
);

const expectedEntityCount=Number(root.dataset.entityCount||0);
const expectedRelationCount=Number(root.dataset.relationCount||0);
if(expectedEntityCount&&expectedEntityCount!==payload.entities.length)
throw new Error(
`entity count mismatch: page=${expectedEntityCount}, asset=${payload.entities.length}`
);
if(expectedRelationCount&&expectedRelationCount!==payload.relations.length)
throw new Error(
`relation count mismatch: page=${expectedRelationCount}, asset=${payload.relations.length}`
);

const entities=new Map(
payload.entities.map(entity=>[entity.id,entity])
);
const edges=new Map();

payload.relations.forEach(relation=>{
if(
!entities.has(relation.source)||
!entities.has(relation.target)
)throw new Error(
`dangling browser projection relation: ${relation.id}`
);

[relation.source,relation.target].forEach(id=>{
if(!edges.has(id))edges.set(id,[]);
edges.get(id).push(relation);
});
});

edges.forEach(items=>items.sort(
(a,b)=>`${a.type}:${a.id}`.localeCompare(
`${b.type}:${b.id}`
)
));

const direct=id=>edges.get(id)||[];

const inspect=entity=>{
inspector.replaceChildren(
el('span','pl-card-kicker','Entity inspector'),
el('h3','',entity.name),
el('code','pl-kg-entity-id',entity.id)
);

if(entity.description)
inspector.append(
el('p','pl-card-lead',entity.description)
);

const facts=el('div','pl-fact-grid');

[
['Type',entity.type],
['Domain',entity.domain||'unassigned'],
['Confidence',entity.confidence||'unvalidated']
].forEach(([label,value])=>
add(
facts,
add(
el('div','pl-fact'),
el('span','',label),
el('strong','',value)
)
)
);

inspector.append(
facts,
el('h4','','Source provenance')
);

const sources=el('div','pl-chip-list');
const sourceItems=entity.source_refs?.length
?entity.source_refs
:['No source ref recorded'];

sourceItems.forEach(source=>
sources.append(
el(
entity.source_refs?.length?'code':'span',
entity.source_refs?.length
?'pl-chip pl-chip--code'
:'pl-chip pl-chip--muted',
source
)
)
);

inspector.append(sources);

const all=direct(entity.id);
const shown=all.slice(0,80);
const stack=el('div','pl-kg-relation-stack');

inspector.append(
el('h4','',`Direct relationships (${all.length})`)
);

shown.forEach(relation=>{
const outbound=relation.source===entity.id;
const otherId=outbound
?relation.target
:relation.source;
const other=entities.get(otherId);
const card=el('details','pl-kg-relation-card');

add(
card,
add(
el('summary'),
el(
'span',
'pl-kg-direction',
outbound?'→':'←'
),
el('code','',relation.type),
el('strong','',other?.name||otherId)
)
);

const detail=el('div','pl-detail-list');

[
['Stable relation ID',relation.id],
['Direction',outbound?'outgoing':'incoming'],
['Other entity',otherId],
[
'Derivation',
relation.derivation?.method||'unvalidated'
],
[
'Generator',
relation.derivation?.generator||'unvalidated'
]
].forEach(([label,value])=>
add(
detail,
add(
el('div','pl-detail-row'),
el('div','',label),
el('div','',value)
)
)
);

const evidence=el('div','pl-chip-list');
const evidenceItems=relation.evidence?.length
?relation.evidence
:['No relation evidence recorded'];

evidenceItems.forEach(item=>
evidence.append(
el(
relation.evidence?.length?'code':'span',
relation.evidence?.length
?'pl-chip pl-chip--code'
:'pl-chip pl-chip--muted',
item
)
)
);

add(
detail,
add(
el('div','pl-detail-row'),
el('div','','Evidence'),
evidence
)
);

add(stack,add(card,detail));
});

if(!shown.length)
stack.append(
el(
'p',
'pl-muted',
'No direct graph relationships are recorded.'
)
);

if(all.length>shown.length)
stack.append(
el(
'p',
'pl-muted',
`Showing first ${shown.length} direct relationships; refine the relationship filter to narrow the view.`
)
);

inspector.append(stack);
};

const render=()=>{
const term=String(
search?.value||''
).trim().toLowerCase();

const filters=[
type?.value,
domain?.value,
confidence?.value
];

const matches=payload.entities.filter(entity=>
(
!term||
`${entity.name} ${entity.id}`
.toLowerCase()
.includes(term)
)&&
(!filters[0]||entity.type===filters[0])&&
(!filters[1]||entity.domain===filters[1])&&
(!filters[2]||entity.confidence===filters[2])&&
(
!relType?.value||
direct(entity.id).some(
relation=>relation.type===relType.value
)
)
).slice(0,30);

results.replaceChildren(
el(
'p',
'pl-kg-result-summary',
`${matches.length}${matches.length===30?'+':''} matching entities shown`
)
);

if(!matches.length){
results.append(
add(
el('div','pl-empty-state'),
el('strong','','No matching canonical entity'),
el(
'p',
'',
'Change filters or search by a stable entity ID. No fuzzy semantic relationship is invented.'
)
)
);
return;
}

matches.forEach(entity=>{
const button=add(
el('button','pl-kg-result'),
el('strong','',entity.name),
el('code','',entity.id),
el(
'small',
'',
`${entity.type} · ${entity.domain||'unassigned'} · ${entity.confidence}`
)
);

button.type='button';
button.addEventListener(
'click',
()=>inspect(entity)
);
results.append(button);
});
};

[
search,
type,
domain,
relType,
confidence
].forEach(control=>
control?.addEventListener(
control===search?'input':'change',
render
)
);

render();
})
.catch(error=>fail(
`Generated same-origin explorer asset could not be loaded safely: ${error.message}`
));
};

  const enhanceAudienceIdentity = () => {
    const content = document.querySelector('.md-content__inner');
    if (!content || content.querySelector('.pl-audience-banner')) return;
    const path = window.location.pathname;
    const audience = path.includes('/generated/production/') || path.includes('/generated/enterprise/threat-model/') || path.includes('/generated/enterprise/operate/') || path.includes('/generated/enterprise/knowledgebase/')
      ? 'production'
      : path.includes('/generated/development/') || path.includes('/generated/enterprise/engineering/') || path.includes('/generated/enterprise/documentation-platform/')
        ? 'development'
        : null;
    if (!audience) return;
    const banner = document.createElement('div');
    banner.className = `pl-audience-banner pl-audience-banner--${audience}`;
    banner.setAttribute('role', 'note');
    if (audience === 'production') {
      banner.innerHTML = '<strong>POCKET LAB LITE · Production Knowledge</strong><small>Operational · evidence-backed · sanitized · release-aware</small>';
    } else {
      banner.innerHTML = '<strong>POCKET LAB LITE · Engineering Reference</strong><small>Source-derived · contracts · validation · implementation detail</small>';
    }
    content.prepend(banner);
  };

  const enhance = () => {
    observeProgressBars();
    enhanceAccessibility();
    enhanceIntentNavigation();
    enhanceScrollableTables();
    enhanceAudienceIdentity();
    enhanceKnowledgeGraph();
  };

  if (typeof document$ !== 'undefined') document$.subscribe(enhance);
  else document.addEventListener('DOMContentLoaded', enhance);
})();

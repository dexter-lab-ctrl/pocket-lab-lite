---
title: "Documentation page types"
description: "Machine-enforced page anatomy contract."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Page types

<div class="pl-page-lede"><strong>Consistent anatomy is a usability and evidence-control feature.</strong><p>Each generated page type has a predictable reading order so operators, developers and reviewers can find the same kind of information in the same place.</p></div>

<div class="pl-page-type-grid">
<article class="pl-page-type-card"><span class="pl-card-kicker">Operational understanding</span><h2>Domain page</h2><p>Use when explaining what an area is, what state it is in, and how to recover safely.</p><div class="pl-anatomy-flow"><span>1<strong>summary</strong></span><span>2<strong>current state</strong></span><span>3<strong>capabilities</strong></span><span>4<strong>dependencies</strong></span><span>5<strong>evidence</strong></span><span>6<strong>known limitations</strong></span><span>7<strong>recovery</strong></span><span>8<strong>provenance</strong></span></div></article>
<article class="pl-page-type-card"><span class="pl-card-kicker">Incident response</span><h2>Runbook page</h2><p>Use when an operator needs a bounded diagnostic and recovery path.</p><div class="pl-anatomy-flow"><span>1<strong>symptom</strong></span><span>2<strong>impact</strong></span><span>3<strong>likely causes</strong></span><span>4<strong>safe checks</strong></span><span>5<strong>recovery</strong></span><span>6<strong>verification</strong></span><span>7<strong>rollback</strong></span><span>8<strong>escalation</strong></span><span>9<strong>evidence</strong></span></div></article>
<article class="pl-page-type-card"><span class="pl-card-kicker">Security reasoning</span><h2>Threat model page</h2><p>Use when reviewing trust boundaries, controls, and unresolved security risk.</p><div class="pl-anatomy-flow"><span>1<strong>boundary</strong></span><span>2<strong>assets</strong></span><span>3<strong>actors</strong></span><span>4<strong>entry points</strong></span><span>5<strong>allowed flows</strong></span><span>6<strong>forbidden flows</strong></span><span>7<strong>threats</strong></span><span>8<strong>controls</strong></span><span>9<strong>runtime evidence</strong></span><span>10<strong>residual risk</strong></span><span>11<strong>review status</strong></span></div></article>
</div>

!!! info "Enforcement"
    The generator remains the source of page anatomy. Generated pages should not bypass these structures with hand-maintained one-off layouts.

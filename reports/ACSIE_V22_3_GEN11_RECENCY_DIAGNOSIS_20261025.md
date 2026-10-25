# V22.3 Gen11 Recency Diagnosis and Evidence — 2026-10-25

**Disposition: H7 UNRESOLVED — NOT QUALIFIED — DO NOT PROMOTE.** No Kaggle kernel was launched. This update changes diagnostic telemetry only; it does not change search order, selection, target generation, gates, thresholds, or denominators.

## Verified Gen9–11 replay

| Gen | Closure rows | Competence | Reuse | Traps | Probes | Probe reuse | Selected primary | Selected parent gens | Target-parent gens | Recency gate | Runtime s |
|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---:|
| 9 | 45/45 | 45/45 (1.0000) | 45/45 (1.0000) | 0 | 4/4 | 1.0 | prim:1c9f1097608c3f094303 | [7, 8] | [8, 7] | PASS | 115.351 |
| 10 | 55/55 | 55/55 (1.0000) | 55/55 (1.0000) | 0 | 4/4 | 1.0 | prim:26db1445ec125612c47d | [9, 8] | [8, 0] | PASS | 191.447 |
| 11 | 66/66 | 66/66 (1.0000) | 66/66 (1.0000) | 0 | 4/4 | 1.0 | prim:c9dafc04ed6c1eaa2115 | [8, 3] | [3, 4] | FAIL | 268.747 |

Checkpoint: dataset #11 and dataset #12 evidence/gen8-resume-checkpoint.json are byte-identical: SHA-256 9fa4cdd87ab5039ac6a9bda6e8f65211f1b077622d5a4feb573a30a342c96818, size 17,589,621 bytes. The restored checkpoint carries Gen0–Gen8 generation rows; Gen9–Gen11 are from the full 166-pair/12-probe replay.

## Why every_closure_perfect is false

| Gen | Pair count | Closure success rate | Closure reuse rate | Closure traps | Perfect? |
|---:|---:|---:|---:|---:|---|
| 0 | 0 | 0.0000 | 0.0000 | 0 | PASS |
| 1 | 1 | 1.0000 | 1.0000 | 0 | PASS |
| 2 | 3 | 1.0000 | 1.0000 | 0 | PASS |
| 3 | 6 | 1.0000 | 1.0000 | 0 | PASS |
| 4 | 10 | 1.0000 | 1.0000 | 0 | PASS |
| 5 | 15 | 0.9333 | 0.9333 | 0 | **FAIL** |
| 6 | 21 | 0.8571 | 0.8571 | 0 | **FAIL** |
| 7 | 28 | 0.7857 | 0.6786 | 3 | **FAIL** |
| 8 | 36 | 0.6667 | 0.5833 | 3 | **FAIL** |
| 9 | 45 | 1.0000 | 1.0000 | 0 | PASS |
| 10 | 55 | 1.0000 | 1.0000 | 0 | PASS |
| 11 | 66 | 1.0000 | 1.0000 | 0 | PASS |

It is not one row: Gen5 and Gen6 are below 1.0; Gen7 and Gen8 are below 1.0 and each has three closure traps. Gen0 is exempt because closure_pair_count == 0. Gen9–Gen11 are perfect in this replay.

## Root-cause assessment: no proof of old-pair behavioral shadowing yet

The active H7 class is OpenEndedRecursiveCognitiveCompiler. Its override invent_primitive() calls find_exact_expression() in behavioral_search.py; it does not call the base compiler _exprs() method shown below. _exprs() does structural JSON deduplication across its three streams, but that method is not the active H7 primary-invention path for this runtime.

The active behavioral search has a dedicated pair_signature_archive keyed by discovery-output context and direct-macro signature, then reintroduces distinct pair signatures into target_frontier before the general alternatives cap. The post-search _h7_pair_signature_preserving_specs() also keeps every shallow two-macro direct signature present in result.alternatives. This is evidence against assuming that an old pair necessarily shadows a recent pair; it is not proof that no recent depth-3 candidate was dropped earlier in the search.

Gen11 target parents are generations [3, 4] (prim:b9f3c773c769732d845e, prim:4a74eb1f189c78ff450e). The selected candidate is prim:c9dafc04ed6c1eaa2115, direct parents [8, 3] (prim:9759420bfb5bc95dcb96, prim:b9f3c773c769732d845e). The persisted summary records 57 discovery-fitting alternatives, 0 recency-eligible, 57 recency-ineligible. Only the first 32 pair diagnostics were persisted before this telemetry patch, so the exact complete 57-expression list and AST depths cannot honestly be reconstructed from the current artifact alone.

### Active H7 invention method (exact source lines 211–359)
~~~python
211:     def invent_primitive(
212:         self,
213:         train: Sequence,
214:         holdout: Sequence,
215:         transfer: Sequence,
216:         semantics: str = "delta",
217:     ) -> CognitivePrimitive | None:
218:         if len(train) < 6:
219:             return None
220:
221:         discovery_rows = tuple(train)
222:         max_depth = max(3, int(self.meta_policy["max_depth"]) + 1)
223:         previous_horizon = getattr(self, "_h7_search_primary_chain_horizon", None)
224:         self._h7_search_primary_chain_horizon = len(self._h7_primary_macro_ids) + 1
225:         try:
226:             result = find_exact_expression(
227:                 self,
228:                 discovery_rows,
229:                 max_depth,
230:                 require_macro=bool(self.generation > 0 and self.primitives),
231:                 # Wider discovery-only alternative pool for the lineage-diverse readout.
232:                 max_alternatives=32,
233:             )
234:         finally:
235:             if previous_horizon is None:
236:                 self.__dict__.pop("_h7_search_primary_chain_horizon", None)
237:             else:
238:                 self._h7_search_primary_chain_horizon = previous_horizon
239:         if result is None:
240:             self.last_primitive_candidate_frontier = ()
241:             return None
242:
243:         def error(rows: Sequence, expression: Mapping[str, object]) -> float:
244:             if not rows:
245:                 return float("inf")
246:             vals = []
247:             pmap = self._pmap()
248:             for trace in rows:
249:                 try:
250:                     vals.append(abs(eval_expr(expression, trace.inputs, pmap) - trace.target))
251:                 except Exception:
252:                     return float("inf")
253:             return sum(vals) / len(vals)
254:
255:         specs = list(result.alternatives) or [(result.expression, result.used_primitives)]
256:         selected_specs = _h7_pair_signature_preserving_specs(specs, non_pair_cap=8)
257:         # For the frozen Gen9-11 recency check, order only discovery-fitting
258:         # alternatives by the recorded primary-chain pair eligibility predicate.
259:         # No target labels, held-out rows, transfer/OOD results, or post-selection
260:         # admission outcomes enter this order. Stable index preserves all existing
261:         # tie-breaks among candidates with the same recency status.
262:         recency_candidate_rows = []
263:         candidate_diagnostics = []
264:         if int(self.generation) in (9, 10, 11):
265:             selected_specs = [
266:                 item for _, item in sorted(
267:                     enumerate(selected_specs),
268:                     key=lambda indexed: (
269:                         self._h7_primary_pair_recency_priority(indexed[1][0]),
270:                         indexed[0],
271:                     ),
272:                 )
273:             ]
274:         for expression, used in selected_specs:
275:             direct_ids = {
276:                 str(node["id"]) for node in self._walk(expression)
277:                 if node.get("op") == "macro" and node.get("id") is not None
278:             }
279:             recency_priority = self._h7_primary_pair_recency_priority(expression)
280:             direct_parent_generations = [
281:                 int(getattr(self.primitives.get(pid), "generation", -1))
282:                 if self.primitives.get(pid) is not None else -1
283:                 for pid in sorted(direct_ids)
284:             ]
285:             detail = {
286:                 "expression": copy.deepcopy(expression),
287:                 "ast_depth": int(ast_depth(expression)),
288:                 "ast_nodes": int(ast_nodes(expression)),
289:                 "used_primitives": sorted(set(str(pid) for pid in used)),
290:                 "direct_parent_ids": sorted(direct_ids),
291:                 "direct_parent_generations": direct_parent_generations,
292:                 "recency_priority": int(recency_priority),
293:                 "recency_eligible": recency_priority == 0,
294:             }
295:             candidate_diagnostics.append(detail)
296:             if int(self.generation) in (9, 10, 11) and len(direct_ids) >= 2:
297:                 recency_candidate_rows.append(copy.deepcopy(detail))
298:         frontier: list[CognitivePrimitive] = []
299:         for expression, used in selected_specs:
300:             pid = "prim:" + digest((expression, semantics))[:20]
301:             if pid in self.primitives:
302:                 continue
303:             primitive = CognitivePrimitive(
304:                 pid,
305:                 copy.deepcopy(expression),
306:                 tuple(sorted(set().union(*(t.inputs.keys() for t in discovery_rows)))),
307:                 semantics,
308:                 self.generation,
309:                 tuple(used),
310:                 tuple(sorted({t.family for t in list(train) + list(transfer)})),
311:                 error(train, expression),
312:                 error(holdout, expression),
313:                 error(transfer, expression),
314:                 ast_nodes(expression),
315:                 {
316:                     "origin": "open_ended_behavioral_dp_search",
317:                     "schema_given": False,
318:                     "external_model": False,
319:                     "selection_source": "discovery_and_selection_only",
320:                     "ood_used_for_selection": False,
321:                     "validation_evaluated_after_selection": True,
322:                     "validation_role": "admission_only",
323:                     "candidate_frontier_size": len(selected_specs),
324:                     "pair_signature_archive_count": sum(
325:                         1 for expression, used in selected_specs
326:                         if ast_depth(expression) <= 2 and len(set(used)) == 2
327:                     ),
328:                     "direct_parent_ids": list(used),
329:                     "search_stats": dict(result.stats),
330:                 },
331:             )
332:             self.primitives[pid] = primitive
333:             self.archive[pid] = ArchiveRecord(primitive)
334:             frontier.append(primitive)
335:
336:         self.last_search_stats = dict(result.stats)
337:         self.last_primitive_candidate_frontier = tuple(frontier)
338:         if int(self.generation) in (9, 10, 11):
339:             selected = frontier[0] if frontier else None
340:             selected_ids = list(getattr(selected, "parent_ids", ())) if selected is not None else []
341:             selected_generations = [
342:                 int(getattr(self.primitives.get(pid), "generation", -1))
343:                 if self.primitives.get(pid) is not None else -1
344:                 for pid in selected_ids
345:             ]
346:             self._h7_primitive_invention_summary = {
347:                 "generation": int(self.generation),
348:                 "source": "OpenEndedRecursiveCognitiveCompiler.invent_primitive",
349:                 "discovery_fitting_alternative_count": len(specs),
350:                 "selected_frontier_count_after_signature_preserving": len(selected_specs),
351:                 "recency_eligible_discovery_candidate_count": sum(
352:                     row["recency_eligible"] for row in recency_candidate_rows
353:                 ),
354:                 "recency_ineligible_discovery_candidate_count": sum(
355:                     not row["recency_eligible"] for row in recency_candidate_rows
356:                 ),
357:                 # Keep the legacy 32-row sample for compatibility, but also persist
358:                 # the complete discovery-qualified pair list and every returned
359:                 # candidate expression. This is diagnostic-only: it does not alter
~~~

### Base compiler structural enumeration/dedup method (exact source lines 180–335; not the active H7 invention call)
~~~python
180:         Candidate order is the legacy order (specialized frontier first, then
181:         the generic grammar stream). Since callers only consume the first 3000
182:         unique structural expressions, generation stops as soon as that prefix
183:         is complete instead of building and JSON-deduplicating every later AST.
184:         """
185:         # Protect all explicit bootstrap IDs as well as the ordered accepted
186:         # primary chain. Older checkpoints may retain a bootstrap root in a
187:         # separate provenance field rather than in _h7_primary_macro_ids.
188:         inventory_ids = set(str(x) for x in primitive_ids)
189:         primary_order = tuple(
190:             str(pid) for pid in getattr(self, "_h7_primary_macro_ids", ())
191:             if str(pid) in inventory_ids
192:         )
193:         bootstrap_order = self._h7_explicit_bootstrap_macro_ids(primitive_ids)
194:         protected_order = tuple(dict.fromkeys(bootstrap_order + primary_order))
195:         inventory_order = tuple(str(pid) for pid in primitive_ids)
196:         cache_key=(tuple(sorted(keys)),inventory_order,int(depth_limit),primary_order,bootstrap_order)
197:         if cache_key in self._expr_cache:
198:             return self._expr_cache[cache_key]
199:
200:         atoms=self._expr_atoms(keys,primitive_ids)
201:         macros=[a for a in atoms if a.get("op")=="macro"]
202:         macro_by_id = {str(a["id"]): a for a in macros}
203:         primary_macros = [macro_by_id[pid] for pid in primary_order if pid in macro_by_id]
204:         protected_macros = [macro_by_id[pid] for pid in protected_order if pid in macro_by_id]
205:         consts=[a for a in atoms if a.get("op")=="const"]
206:         gets=[a for a in atoms if a.get("op")=="get"]
207:         binary_ops=("add","sub","mul","max","min")
208:
209:         def pair_nodes():
210:             for a in gets:
211:                 for b in gets:
212:                     for op in ("add","sub","mul"):
213:                         yield {"op":op,"left":a,"right":b}
214:
215:         def specialized_frontier():
216:             # Preserve generic macro-macro compositions ahead of the global
217:             # insertion-order budget. This is not target-directed: every pair
218:             # of currently known macros receives the same operator set.
219:             for a in macros:
220:                 for b in macros:
221:                     for op in binary_ops:
222:                         yield {"op":op,"left":a,"right":b}
223:
224:             for a in gets:
225:                 for b in gets:
226:                     yield {"op":"add","left":a,"right":b}
227:                     yield {"op":"sub","left":a,"right":b}
228:                     yield {"op":"mul","left":a,"right":b}
229:                 for c in consts:
230:                     yield {"op":"mul","left":a,"right":c}
231:                     yield {"op":"add","left":a,"right":c}
232:                     yield {"op":"sub","left":a,"right":c}
233:
234:             for d in pair_nodes():
235:                 for a in gets:
236:                     yield {"op":"add","left":d,"right":a}
237:                     yield {"op":"add","left":a,"right":d}
238:                     yield {"op":"sub","left":d,"right":a}
239:                     yield {"op":"mul","left":d,"right":a}
240:
241:             for m in macros:
242:                 for c in consts:
243:                     yield {"op":"mul","left":m,"right":c}
244:                     yield {"op":"mul","left":c,"right":m}
245:                     yield {"op":"add","left":m,"right":c}
246:                     yield {"op":"sub","left":m,"right":c}
247:                     for fexpr in (
248:                         {"op":"mul","left":m,"right":c},
249:                         {"op":"add","left":m,"right":c},
250:                     ):
251:                         for c2 in consts[:4]:
252:                             yield {"op":"add","left":fexpr,"right":c2}
253:                             yield {"op":"mul","left":fexpr,"right":c2}
254:
255:         def generic_stream():
256:             yield from atoms
257:             if depth_limit>=2:
258:                 # Generic language closure: unary expressions precede all
259:                 # atom-pair expressions, matching the legacy ordering.
260:                 for a in atoms:
261:                     for op in ("abs","neg"):
262:                         yield {"op":op,"arg":a}
263:                 for a in atoms:
264:                     for b in atoms:
265:                         for op in binary_ops:
266:                             yield {"op":op,"left":a,"right":b}
267:
268:             if depth_limit>=3:
269:                 # These are exactly the depth-two expressions created above,
270:                 # streamed in their original order without retaining a d2 list.
271:                 def depth_two_stream():
272:                     for a in atoms:
273:                         for op in ("abs","neg"):
274:                             yield {"op":op,"arg":a}
275:                     for a in atoms:
276:                         for b in atoms:
277:                             for op in binary_ops:
278:                                 yield {"op":op,"left":a,"right":b}
279:
280:                 for expr in depth_two_stream():
281:                     for op in ("abs","neg"):
282:                         yield {"op":op,"arg":expr}
283:                     for a in atoms:
284:                         for op in binary_ops:
285:                             yield {"op":op,"left":expr,"right":a}
286:                             yield {"op":op,"left":a,"right":expr}
287:
288:         def primary_pair_frontier():
289:             # Protect target-independent ordered pairs from both explicitly
290:             # recorded bootstrap vocabulary and the accepted primary chain.
291:             # These labels affect enumeration order only; discovery rows still
292:             # decide whether each generated expression is retained.
293:             if depth_limit < 2:
294:                 return
295:             for a in protected_macros:
296:                 for b in protected_macros:
297:                     for op in binary_ops:
298:                         yield {"op":op,"left":a,"right":b}
299:
300:         values: list[Mapping[str,Any]] = []
301:         seen: set[str] = set()
302:         primary_pair_expression_count = len(primary_macros) * len(primary_macros) * len(binary_ops)
303:         protected_pair_expression_count = len(protected_macros) * len(protected_macros) * len(binary_ops)
304:         for stream in (primary_pair_frontier(), specialized_frontier(), generic_stream()):
305:             for expr in stream:
306:                 structural = json.dumps(expr,sort_keys=True)
307:                 if structural in seen:
308:                     continue
309:                 seen.add(structural)
310:                 values.append(expr)
311:                 if len(values)>=3000:
312:                     break
313:             if len(values)>=3000:
314:                 break
315:
316:         self._expr_cache[cache_key]=values
317:         self._expr_enumeration_summary = {
318:             "candidate_limit": 3000,
319:             "returned_unique_expression_count": len(values),
320:             "limit_reached": len(values) >= 3000,
321:             "primary_macro_count": len(primary_macros),
322:             "primary_pair_expression_count": primary_pair_expression_count,
323:             "bootstrap_macro_count": len(bootstrap_order),
324:             "bootstrap_macro_ids": list(bootstrap_order),
325:             "protected_macro_count": len(protected_macros),
326:             "protected_pair_expression_count": protected_pair_expression_count,
327:             "primary_pair_prefix_exceeds_limit": protected_pair_expression_count > 3000,
328:             "chain_order_sha256": __import__("hashlib").sha256(
329:                 json.dumps(list(primary_order),separators=(",",":")).encode("utf-8")
330:             ).hexdigest(),
331:             "protected_pair_order_sha256": __import__("hashlib").sha256(
332:                 json.dumps(list(protected_order),separators=(",",":")).encode("utf-8")
333:             ).hexdigest(),
334:         }
335:         return values
~~~

### Behavioral pair-signature archive excerpt
~~~python
1274:     def _h7_archive_alias_candidate(state: tuple) -> None:
1275:         context = (tuple(state[1]), tuple(state[3]))
1276:         direct_signature = tuple(sorted(set(state[2])))
1277:         meta = _H7_meta(state)
1278:         if int(meta["ast_depth"]) <= 2 and len(direct_signature) == 2:
1279:             pair_bucket = pair_signature_archive.setdefault(context, {})
1280:             old_pair = pair_bucket.get(direct_signature)
1281:             pair_key = (
1282:                 int(meta["ast_depth"]), int(meta["depth"]), int(meta["nodes"]),
1283:                 json.dumps(state[0], sort_keys=True, separators=(",", ":")),
1284:             )
1285:             old_pair_key = None
1286:             if old_pair is not None:
1287:                 old_meta = _H7_meta(old_pair)
1288:                 old_pair_key = (
1289:                     int(old_meta["ast_depth"]), int(old_meta["depth"]), int(old_meta["nodes"]),
1290:                     json.dumps(old_pair[0], sort_keys=True, separators=(",", ":")),
1291:                 )
1292:             if old_pair is None or pair_key < old_pair_key:
1293:                 pair_bucket[direct_signature] = state
1294:                 if old_pair is None:
1295:                     stats["pair_signature_archive_state_count"] += 1
1296:                 stats["pair_signature_archive_context_count"] = len(pair_signature_archive)
1297:                 stats["pair_signature_archive_max_per_context"] = max(
1298:                     int(stats["pair_signature_archive_max_per_context"]), len(pair_bucket)
1299:                 )
1300:         bucket = passive_alias_archive.setdefault(context, {})
~~~
~~~python
3547:         for context, signature_bucket in passive_alias_archive.items():
3548:             if context[0] != target:
3549:                 continue
3550:             for state in signature_bucket.values():
3551:                 if state[1] == target and (not require_macro or state[2]):
3552:                     target_states_by_token[state[5]] = state
3553:         target_pair_archive_states: dict[tuple[str, ...], tuple] = {}
3554:         for context, signature_bucket in pair_signature_archive.items():
3555:             if context[0] != target:
3556:                 continue
3557:             for direct_signature, state in signature_bucket.items():
3558:                 if state[1] != target or (require_macro and not state[2]):
3559:                     continue
3560:                 old_pair = target_pair_archive_states.get(direct_signature)
3561:                 if old_pair is None:
3562:                     target_pair_archive_states[direct_signature] = state
3563:                 else:
3564:                     old_meta = _H7_meta(old_pair)
3565:                     meta = _H7_meta(state)
3566:                     candidate_key = (
3567:                         int(meta["ast_depth"]), int(meta["depth"]), int(meta["nodes"]),
3568:                         json.dumps(state[0], sort_keys=True, separators=(",", ":")),
3569:                     )
3570:                     old_key = (
3571:                         int(old_meta["ast_depth"]), int(old_meta["depth"]), int(old_meta["nodes"]),
3572:                         json.dumps(old_pair[0], sort_keys=True, separators=(",", ":")),
3573:                     )
3574:                     if candidate_key < old_key:
3575:                         target_pair_archive_states[direct_signature] = state
3576:                 target_states_by_token[state[5]] = state
3577:         stats["target_pair_signature_archive_count"] = len(target_pair_archive_states)
3578:         for state in target_alternative_representatives.values():
3579:             if state[1] == target and (not require_macro or state[2]):
3580:                 target_states_by_token[state[5]] = state
~~~

### Hidden target generation and discovery split
~~~python
542:     def hidden_library() -> dict[str, dict[str, Any]]:
543:         return {cap.hidden_id: cap.expression for cap in retained}
544:
545:     def capability_macro(cap: HiddenCapability) -> dict[str, Any]:
546:         return {"op": "macro", "id": cap.hidden_id}
547:
548:     for generation in range(start_generation, generations):
549:         generation_wall_started = time.perf_counter()
550:         learner.generation = generation
551:         generation_begin_metrics = _h7_runtime_metrics(learner)
552:         _h7_emit_event(
553:             "GENERATION_BEGIN",
554:             seed=seed,
555:             generation=generation,
556:             timestamp_monotonic_seconds=time.monotonic(),
557:             **generation_begin_metrics,
558:         )
559:         # Emit an audit entry before the expensive discovery/admission work so a
560:         # bounded timeout still leaves a durable trace even if no pair starts.
561:         _h7_emit_event(
562:             "AUDIT_BEGIN",
563:             seed=seed,
564:             generation=generation,
565:             phase="GENERATION_ENTRY_PRE_DISCOVERY",
566:             required_pair_count=generation * (generation + 1) // 2,
567:             planned_pair_count=None,
568:             audit_complete=False,
569:             **generation_begin_metrics,
570:         )
571:         hidden_macros = hidden_library()
572:
573:         target_parents: tuple[HiddenCapability, ...]
574:         if not retained:
575:             target_parents = ()
576:             target = hard_bootstrap_expr(rng)
577:         elif len(retained) == 1:
578:             target_parents = (retained[0],)
579:             target = {
580:                 "op": rng.choice(("add", "sub", "mul", "max", "min")),
581:                 "left": capability_macro(retained[0]),
582:                 "right": {"op": "get", "key": rng.choice(KEYS)},
583:             }
584:         else:
585:             target_parents = tuple(rng.sample(retained, 2))
586:             target = {
587:                 "op": rng.choice(("add", "sub", "mul", "max", "min")),
588:                 "left": capability_macro(target_parents[0]),
589:                 "right": capability_macro(target_parents[1]),
590:             }
591:
592:         target_depth = expanded_depth(target, hidden_macros)
593:
594:         train = make_traces(
595:             target, seed, generation, "train", 12, 0.0, hidden_macros
596:         )
597:         selection = make_traces(
598:             target, seed, generation, "selection", 8, 0.17, hidden_macros
599:         )
600:         hold = make_traces(
601:             target, seed, generation, "holdout", 6, 0.31, hidden_macros
602:         )
603:         transfer = make_traces(
604:             target, seed, generation, "transfer", 8, -0.57, hidden_macros
605:         )
606:         ood = make_traces(
607:             target, seed, generation, "ood", 8, 0.93, hidden_macros
608:         )
609:
610:         discovery_train = tuple(train) + tuple(selection)
~~~

## Historical kernels and dataset comparison

| Artifact | Status | Gen9 selected primitive | Gen10 selected primitive | Gen11 selected primitive | What can be said about selected pair generations? |
|---|---|---|---|---|---|
| Kernel #20 memorican/acsie-h7-arch-v22-five-seed-qualification-20261023 | CRASHED; NOT_QUALIFIED; 48 generation rows in compact table | prim:0554d5eaeaea8fd440a9 | prim:2a99a640a4caf8f64f59 | prim:275bef7b3109c393f144 | Not recorded in downloaded compact generation table/log; do not infer pair gens from target-parent IDs. |
| Kernel #22 memorican/acsie-h7-arch-v22-gen9-11-checkpoint-continuation | PASSED_GEN0_11_SINGLE_SEED_DIAGNOSTIC; NOT_QUALIFIED_SINGLE_SEED_DIAGNOSTIC_ONLY | prim:1c9f1097608c3f094303 | prim:8e39e69622c8e752417c | prim:c9dafc04ed6c1eaa2115 | Compact continuation JSON records selected IDs and target parents, not the selected primitive direct-parent IDs. Current V22.3 confirms [7,8] for the identical Gen9 ID and [8,3] for the identical Gen11 ID; Gen10 prim:8e39 remains unverified from compact output. |

Kernel #22 target-parent IDs: Gen9 [prim:13e721bf242502d84dcf, prim:9759420bfb5bc95dcb96]; Gen10 [prim:7b9e019ca08c0944c250, prim:9759420bfb5bc95dcb96]; Gen11 [prim:4a74eb1f189c78ff450e, prim:b9f3c773c769732d845e]. These are target-generation parents, not the selected invented primitive parents.

Datasets #11 and #12 both contain the exact same Gen8 checkpoint SHA and byte size above; there is no checkpoint difference.

## Fast v2 cancelled-kernel output check

Exactly one bounded kaggle kernels output memorican/acsie-gen3-foundry-fast attempt was made with an 18-second timeout. It exited 124; only a partial _runtime_src tree was downloaded. No run_kaggle_foundry.log, summary, or seed/generation progress file was obtained, so the requested last 30 log lines are unavailable. No second attempt was made.

## Telemetry-only repair and validation

Added complete candidate_details (expression, AST depth/nodes, direct primitive IDs/generations, recency priority) and full candidate_pair_diagnostics, plus selected find_exact_expression archive/cap statistics, to _h7_primitive_invention_summary. The legacy 32-row sample remains unchanged. Added Phase-0 regression coverage that verifies recency ordering and complete candidate diagnostics. This does not alter candidate enumeration, selection, hidden target generation, gates, thresholds, or denominators.

Build: runner SHA-256 55583d039574810d1c99f2bc96be6ee4f9549e1686b7237e4dcfc82132853952; embedded source archive SHA-256 b0b1fddc060af109e88ec43b03e9afe95c88f7dc3bcbbcb2b8ecda8b59d9c61c; manifest SHA-256 b00b880f0199a44c29a1cb060c83b41600f7bce8cd1d360677637599549d5550. Phase-0: 24/24 tests passed, compile passed, research_started=false, qualification_slots_evaluated=0, kaggle_dispatch_performed=false.

Next step: use an authorized remote compute target for a focused Gen11 candidate-diagnostic replay, inspect all 57+ candidate expressions and find_exact_expression archive counts, then decide whether a search-retention algorithm change is justified. Do not launch qualification and do not promote.

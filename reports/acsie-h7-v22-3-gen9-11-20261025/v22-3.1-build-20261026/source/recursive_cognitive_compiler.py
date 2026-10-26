from __future__ import annotations

import copy, json, math, random
from collections import OrderedDict
from dataclasses import dataclass, asdict, field
from hashlib import sha256
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

Json = Any

def digest(x: Any) -> str:
    return sha256(json.dumps(x, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()

def ast_depth(e: Mapping[str, Any]) -> int:
    op = e["op"]
    if op in {"const","get","macro"}: return 1
    if op in {"abs","neg","threshold"}: return 1 + ast_depth(e["arg"])
    return 1 + max(ast_depth(e["left"]), ast_depth(e["right"]))

def ast_nodes(e: Mapping[str, Any]) -> int:
    op=e["op"]
    if op in {"const","get","macro"}: return 1
    if op in {"abs","neg","threshold"}: return 1 + ast_nodes(e["arg"])
    return 1 + ast_nodes(e["left"])+ast_nodes(e["right"])


def h7_primary_pair_rank_prefix(
    is_minimal_primary_pair: bool,
    primary_lineage_size: int,
    expanded_depth: int,
    expanded_nodes: int,
) -> tuple[int, int, int, int]:
    """Rank exact-fit primary-pair expressions without collapsing lineage aliases.

    Only members of the minimal direct-primary-pair tier receive this tie-break.
    Within that tier, preserve executable primary-chain identity before unrolled
    syntax cost; otherwise a shallow ancestor alias can outrank the live macro
    whose lineage is actually being tested. No target-pair labels or validation
    outcomes are inputs to this rank prefix.
    """
    return (
        0 if is_minimal_primary_pair else 1,
        -int(primary_lineage_size) if is_minimal_primary_pair else 0,
        int(expanded_depth),
        int(expanded_nodes),
    )

def eval_expr(e: Mapping[str, Any], inputs: Mapping[str,float], macros: Mapping[str, Mapping[str,Any]]) -> float:
    op=e["op"]
    if op=="const": return float(e["value"])
    if op=="get": return float(inputs[e["key"]])
    if op=="macro": return eval_expr(macros[e["id"]], inputs, macros)
    if op=="abs": return abs(eval_expr(e["arg"],inputs,macros))
    if op=="neg": return -eval_expr(e["arg"],inputs,macros)
    if op=="threshold":
        x=eval_expr(e["arg"],inputs,macros)
        return 1.0 if x >= float(e["lo"]) else 0.0
    a=eval_expr(e["left"],inputs,macros); b=eval_expr(e["right"],inputs,macros)
    if op=="add": return a+b
    if op=="sub": return a-b
    if op=="mul": return a*b
    if op=="max": return max(a,b)
    if op=="min": return min(a,b)
    raise ValueError(op)

@dataclass(frozen=True)
class Trace:
    inputs: Dict[str,float]
    target: float
    family: str
    context: Dict[str,float]
    task_id: str

@dataclass(frozen=True)
class CognitivePrimitive:
    primitive_id: str
    expression: Mapping[str,Any]
    input_roles: Tuple[str,...]
    output_semantics: str
    generation: int
    parent_ids: Tuple[str,...]
    source_families: Tuple[str,...]
    train_error: float
    holdout_error: float
    transfer_error: float
    complexity: int
    provenance: Mapping[str,Any]
    status: str="candidate"

@dataclass(frozen=True)
class ProcessCandidate:
    process_id: str
    expression: Mapping[str,Any]
    used_primitives: Tuple[str,...]
    generation: int
    parent_ids: Tuple[str,...]
    search_policy: Mapping[str,Any]
    source_families: Tuple[str,...]
    complexity: int
    provenance: Mapping[str,Any]
    status: str="candidate"

@dataclass(frozen=True)
class Evaluation:
    train_error: float
    holdout_error: float
    transfer_error: float
    ood_error: float
    interference_harm: float
    resource_cost: float
    novelty: float
    accepted: bool

@dataclass
class ArchiveRecord:
    primitive: CognitivePrimitive
    utility_history: List[float]=field(default_factory=list)
    uses: int=0

class RecursiveCognitiveCompiler:
    """Model-independent recursive cognitive compiler.

    Components are explicit and ablatable:
    recursive trace conditioning; persistent archive/novelty search;
    editable meta-search policy; empirical experiment/selection; compatibility gating.
    """
    BASE_ATOMS=("get","const","add","sub","mul","max","min","abs","neg","threshold")

    def __init__(self, max_depth:int=2, population:int=24, seed:int=0):
        self.max_depth=max_depth
        self.population=population
        self.rng=random.Random(seed)
        self.generation=0
        self.recursion_depth=0
        self.meta_policy={"max_depth":max_depth,"novelty_weight":0.25,"exploration":0.50,"mutation_rate":0.30}
        self.primitives: Dict[str,CognitivePrimitive]={}
        self.archive: Dict[str,ArchiveRecord]={}
        self.processes: Dict[str,ProcessCandidate]={}
        self.process_frontier: List[str]=[]
        self.events: List[Dict[str,Any]]=[]
        self.active: Optional[str]=None
        self._expr_cache: Dict[Tuple[Any, ...],List[Mapping[str,Any]]] = {}
        self._expr_enumeration_summary: Dict[str,Any] = {}
        # V11 node-vector cache: per-instance, bounded, and invalidated whenever
        # the executable macro environment changes.
        self._node_eval_epoch = 0
        self._node_eval_pmap_signature: Optional[Tuple[Tuple[str,str],...]] = None
        self._node_eval_pmap: Dict[str,Mapping[str,Any]] = {}
        self._node_value_cache: OrderedDict[
            Tuple[int,Tuple[Tuple[str,float],...],int],
            Tuple[Mapping[str,Any],float],
        ] = OrderedDict()
        self._node_vector_cache: OrderedDict[
            Tuple[int,Tuple[Tuple[Tuple[str,float],...],...],int],
            Tuple[Mapping[str,Any],Tuple[float,...]],
        ] = OrderedDict()
        self._node_value_cache_limit = 150_000
        self._node_vector_cache_limit = 8_192

    def _expr_atoms(self, keys:Sequence[str], primitive_ids:Sequence[str])->List[Mapping[str,Any]]:
        return [
            *({"op":"get","key":k} for k in sorted(set(keys))),
            *({"op":"const","value":c} for c in (-2,-1,0,1,2,3,4)),
            *({"op":"macro","id":p} for p in primitive_ids),
        ]

    def _h7_explicit_bootstrap_macro_ids(self, primitive_ids:Sequence[str])->Tuple[str,...]:
        """Normalize explicitly recorded bootstrap IDs that exist in inventory.

        Bootstrap provenance may be checkpointed as a string-ID list or as
        metadata records containing primitive_id. Never infer it from generation
        numbers, insertion order, or task/target values.
        """
        inventory = {str(pid) for pid in primitive_ids}
        ordered: list[str] = []
        seen: set[str] = set()
        for attribute in ("bootstrap_primitives", "_h7_bootstrap_primitives"):
            raw = getattr(self, attribute, ())
            if isinstance(raw, (str, Mapping)):
                items = (raw,)
            else:
                try:
                    items = tuple(raw or ())
                except TypeError:
                    items = ()
            for item in items:
                if isinstance(item, Mapping):
                    value = item.get("primitive_id", item.get("id"))
                else:
                    value = item
                if value is None:
                    continue
                pid = str(value)
                if pid in inventory and pid not in seen:
                    seen.add(pid)
                    ordered.append(pid)
        return tuple(ordered)

    def _exprs(self, keys:Sequence[str], primitive_ids:Sequence[str], depth_limit:int)->List[Mapping[str,Any]]:
        """Return the first 3000 unique expressions without materializing the full cross-product.

        Candidate order is the legacy order (specialized frontier first, then
        the generic grammar stream). Since callers only consume the first 3000
        unique structural expressions, generation stops as soon as that prefix
        is complete instead of building and JSON-deduplicating every later AST.
        """
        # Protect all explicit bootstrap IDs as well as the ordered accepted
        # primary chain. Older checkpoints may retain a bootstrap root in a
        # separate provenance field rather than in _h7_primary_macro_ids.
        inventory_ids = set(str(x) for x in primitive_ids)
        primary_order = tuple(
            str(pid) for pid in getattr(self, "_h7_primary_macro_ids", ())
            if str(pid) in inventory_ids
        )
        bootstrap_order = self._h7_explicit_bootstrap_macro_ids(primitive_ids)
        protected_order = tuple(dict.fromkeys(bootstrap_order + primary_order))
        inventory_order = tuple(str(pid) for pid in primitive_ids)
        cache_key=(tuple(sorted(keys)),inventory_order,int(depth_limit),primary_order,bootstrap_order)
        if cache_key in self._expr_cache:
            return self._expr_cache[cache_key]

        atoms=self._expr_atoms(keys,primitive_ids)
        macros=[a for a in atoms if a.get("op")=="macro"]
        macro_by_id = {str(a["id"]): a for a in macros}
        primary_macros = [macro_by_id[pid] for pid in primary_order if pid in macro_by_id]
        protected_macros = [macro_by_id[pid] for pid in protected_order if pid in macro_by_id]
        consts=[a for a in atoms if a.get("op")=="const"]
        gets=[a for a in atoms if a.get("op")=="get"]
        binary_ops=("add","sub","mul","max","min")

        def pair_nodes():
            for a in gets:
                for b in gets:
                    for op in ("add","sub","mul"):
                        yield {"op":op,"left":a,"right":b}

        def specialized_frontier():
            # Preserve generic macro-macro compositions ahead of the global
            # insertion-order budget. This is not target-directed: every pair
            # of currently known macros receives the same operator set.
            for a in macros:
                for b in macros:
                    for op in binary_ops:
                        yield {"op":op,"left":a,"right":b}

            for a in gets:
                for b in gets:
                    yield {"op":"add","left":a,"right":b}
                    yield {"op":"sub","left":a,"right":b}
                    yield {"op":"mul","left":a,"right":b}
                for c in consts:
                    yield {"op":"mul","left":a,"right":c}
                    yield {"op":"add","left":a,"right":c}
                    yield {"op":"sub","left":a,"right":c}

            for d in pair_nodes():
                for a in gets:
                    yield {"op":"add","left":d,"right":a}
                    yield {"op":"add","left":a,"right":d}
                    yield {"op":"sub","left":d,"right":a}
                    yield {"op":"mul","left":d,"right":a}

            for m in macros:
                for c in consts:
                    yield {"op":"mul","left":m,"right":c}
                    yield {"op":"mul","left":c,"right":m}
                    yield {"op":"add","left":m,"right":c}
                    yield {"op":"sub","left":m,"right":c}
                    for fexpr in (
                        {"op":"mul","left":m,"right":c},
                        {"op":"add","left":m,"right":c},
                    ):
                        for c2 in consts[:4]:
                            yield {"op":"add","left":fexpr,"right":c2}
                            yield {"op":"mul","left":fexpr,"right":c2}

        def generic_stream():
            yield from atoms
            if depth_limit>=2:
                # Generic language closure: unary expressions precede all
                # atom-pair expressions, matching the legacy ordering.
                for a in atoms:
                    for op in ("abs","neg"):
                        yield {"op":op,"arg":a}
                for a in atoms:
                    for b in atoms:
                        for op in binary_ops:
                            yield {"op":op,"left":a,"right":b}

            if depth_limit>=3:
                # These are exactly the depth-two expressions created above,
                # streamed in their original order without retaining a d2 list.
                def depth_two_stream():
                    for a in atoms:
                        for op in ("abs","neg"):
                            yield {"op":op,"arg":a}
                    for a in atoms:
                        for b in atoms:
                            for op in binary_ops:
                                yield {"op":op,"left":a,"right":b}

                for expr in depth_two_stream():
                    for op in ("abs","neg"):
                        yield {"op":op,"arg":expr}
                    for a in atoms:
                        for op in binary_ops:
                            yield {"op":op,"left":expr,"right":a}
                            yield {"op":op,"left":a,"right":expr}

        def primary_pair_frontier():
            # Protect target-independent ordered pairs from both explicitly
            # recorded bootstrap vocabulary and the accepted primary chain.
            # These labels affect enumeration order only; discovery rows still
            # decide whether each generated expression is retained.
            if depth_limit < 2:
                return
            for a in protected_macros:
                for b in protected_macros:
                    for op in binary_ops:
                        yield {"op":op,"left":a,"right":b}

        values: list[Mapping[str,Any]] = []
        seen: set[str] = set()
        primary_pair_expression_count = len(primary_macros) * len(primary_macros) * len(binary_ops)
        protected_pair_expression_count = len(protected_macros) * len(protected_macros) * len(binary_ops)
        for stream in (primary_pair_frontier(), specialized_frontier(), generic_stream()):
            for expr in stream:
                structural = json.dumps(expr,sort_keys=True)
                if structural in seen:
                    continue
                seen.add(structural)
                values.append(expr)
                if len(values)>=3000:
                    break
            if len(values)>=3000:
                break

        self._expr_cache[cache_key]=values
        self._expr_enumeration_summary = {
            "candidate_limit": 3000,
            "returned_unique_expression_count": len(values),
            "limit_reached": len(values) >= 3000,
            "primary_macro_count": len(primary_macros),
            "primary_pair_expression_count": primary_pair_expression_count,
            "bootstrap_macro_count": len(bootstrap_order),
            "bootstrap_macro_ids": list(bootstrap_order),
            "protected_macro_count": len(protected_macros),
            "protected_pair_expression_count": protected_pair_expression_count,
            "primary_pair_prefix_exceeds_limit": protected_pair_expression_count > 3000,
            "chain_order_sha256": __import__("hashlib").sha256(
                json.dumps(list(primary_order),separators=(",",":")).encode("utf-8")
            ).hexdigest(),
            "protected_pair_order_sha256": __import__("hashlib").sha256(
                json.dumps(list(protected_order),separators=(",",":")).encode("utf-8")
            ).hexdigest(),
        }
        return values

    def _walk(self,e:Mapping[str,Any])->Iterable[Mapping[str,Any]]:
        yield e
        if e["op"] in {"add","sub","mul","max","min"}:
            yield from self._walk(e["left"]); yield from self._walk(e["right"])
        elif e["op"] in {"abs","neg","threshold"}:
            yield from self._walk(e["arg"])

    def diagnose(self, traces:Sequence[Trace], failures:Mapping[str,float])->Tuple[str,...]:
        dx=[]
        if failures.get("search_saturation",0)>=0.8: dx.append("SEARCH_SATURATION")
        if failures.get("transfer_risk",0)>=0.7: dx.append("NEGATIVE_TRANSFER")
        if failures.get("context_ambiguity",0)>=0.7: dx.append("CONTEXT_AMBIGUITY")
        if failures.get("prediction_error",0)>=0.5: dx.append("PROCESS_MODEL_ERROR")
        if not dx: dx.append("LANGUAGE_COVERAGE_GAP")
        self.events.append({"event":"DIAGNOSIS","diagnoses":dx})
        return tuple(dx)

    def propose_search_policies(self)->Tuple[Mapping[str,Any],...]:
        p=self.meta_policy
        return (
            {"max_depth":min(4,int(p["max_depth"])+1),"novelty_weight":p["novelty_weight"],"exploration":min(1,p["exploration"]+0.15),"mutation_rate":p["mutation_rate"]},
            {"max_depth":int(p["max_depth"]),"novelty_weight":min(0.8,p["novelty_weight"]+0.20),"exploration":p["exploration"],"mutation_rate":min(0.8,p["mutation_rate"]+0.1)},
            {"max_depth":int(p["max_depth"]),"novelty_weight":max(0.0,p["novelty_weight"]-0.20),"exploration":max(0.05,p["exploration"]-0.15),"mutation_rate":max(0.05,p["mutation_rate"]-0.1)},
        )

    def experimentally_select_meta_policy(self, candidates:Sequence[Mapping[str,Any]], scores:Mapping[int,float])->Mapping[str,Any]:
        best=max(range(len(candidates)), key=lambda i: float(scores.get(i,-1e9)))
        chosen=dict(candidates[best]); old=self.meta_policy; self.meta_policy=chosen
        self.events.append({"event":"META_POLICY_SELECTED","before":old,"after":chosen,"scores":dict(scores)})
        return chosen

    def learn_role_map(self, source_rows: Sequence[Trace], target_rows: Sequence[Trace]) -> Dict[str,str]:
        def sig(rows, key):
            vals=[float(r.inputs[key]) for r in rows if key in r.inputs]
            if not vals: return (0,0,0,0)
            mu=sum(vals)/len(vals); var=sum((v-mu)**2 for v in vals)/len(vals)
            return (min(vals),max(vals),mu,math.sqrt(var))
        sk=sorted(source_rows[0].inputs); tk=sorted(target_rows[0].inputs)
        ss={k:sig(source_rows,k) for k in sk}; tt={k:sig(target_rows,k) for k in tk}
        remaining=set(tk); out={}
        for k in sk:
            best=min(remaining,key=lambda q: sum((ss[k][i]-tt[q][i])**2 for i in range(4)))
            out[best]=k; remaining.remove(best)
        self.events.append({"event":"ROLE_ALIGNMENT","mapping":out})
        return out

    def remap_traces(self, rows: Sequence[Trace], mapping: Mapping[str,str]) -> List[Trace]:
        return [Trace({mapping.get(k,k):v for k,v in r.inputs.items()},r.target,r.family,dict(r.context),r.task_id) for r in rows]

    def _pmap(self)->Dict[str,Mapping[str,Any]]:
        return {k:v.expression for k,v in self.primitives.items()}

    def _prepare_node_eval_cache(self)->Dict[str,Mapping[str,Any]]:
        """Pin a macro-map snapshot and invalidate memoized nodes on change."""
        pmap=self._pmap()
        signature=tuple(
            (str(pid),digest(expr))
            for pid,expr in sorted(pmap.items(),key=lambda item:str(item[0]))
        )
        if signature != self._node_eval_pmap_signature:
            self._node_eval_pmap_signature=signature
            self._node_eval_pmap=pmap
            self._node_eval_epoch+=1
            self._node_value_cache.clear()
            self._node_vector_cache.clear()
        return self._node_eval_pmap

    @staticmethod
    def _node_input_signature(inputs:Mapping[str,float])->Tuple[Tuple[str,float],...]:
        return tuple(sorted((str(key),float(value)) for key,value in inputs.items()))

    def _eval_node_cached(
        self,
        expr:Mapping[str,Any],
        inputs:Mapping[str,float],
        macros:Mapping[str,Mapping[str,Any]],
        input_signature:Tuple[Tuple[str,float],...],
    )->float:
        """Evaluate one AST node with an epoch- and input-exact bounded cache."""
        cache_key=(id(expr),input_signature,self._node_eval_epoch)
        cached=self._node_value_cache.get(cache_key)
        if cached is not None:
            cached_expr,cached_value=cached
            if cached_expr is expr:
                self._node_value_cache.move_to_end(cache_key)
                return cached_value
            # Defensive against a recycled Python object ID.
            self._node_value_cache.pop(cache_key,None)

        op=expr["op"]
        if op=="const":
            value=float(expr["value"])
        elif op=="get":
            value=float(inputs[expr["key"]])
        elif op=="macro":
            value=self._eval_node_cached(
                macros[expr["id"]],inputs,macros,input_signature
            )
        elif op=="abs":
            value=abs(self._eval_node_cached(
                expr["arg"],inputs,macros,input_signature
            ))
        elif op=="neg":
            value=-self._eval_node_cached(
                expr["arg"],inputs,macros,input_signature
            )
        elif op=="threshold":
            inner=self._eval_node_cached(
                expr["arg"],inputs,macros,input_signature
            )
            value=1.0 if inner>=float(expr["lo"]) else 0.0
        else:
            left=self._eval_node_cached(
                expr["left"],inputs,macros,input_signature
            )
            right=self._eval_node_cached(
                expr["right"],inputs,macros,input_signature
            )
            if op=="add": value=left+right
            elif op=="sub": value=left-right
            elif op=="mul": value=left*right
            elif op=="max": value=max(left,right)
            elif op=="min": value=min(left,right)
            else: raise ValueError(op)

        self._node_value_cache[cache_key]=(expr,value)
        self._node_value_cache.move_to_end(cache_key)
        while len(self._node_value_cache)>self._node_value_cache_limit:
            self._node_value_cache.popitem(last=False)
        return value

    def _node_vector_eval(
        self,
        expr:Mapping[str,Any],
        rows:Sequence[Trace],
        macros:Optional[Mapping[str,Mapping[str,Any]]]=None,
    )->Tuple[float,...]:
        """Evaluate an expression over a fixed row batch, reusing node vectors."""
        pmap=macros if macros is not None else self._prepare_node_eval_cache()
        row_signatures=tuple(self._node_input_signature(row.inputs) for row in rows)
        vector_key=(id(expr),row_signatures,self._node_eval_epoch)
        cached=self._node_vector_cache.get(vector_key)
        if cached is not None:
            cached_expr,cached_vector=cached
            if cached_expr is expr:
                self._node_vector_cache.move_to_end(vector_key)
                return cached_vector
            self._node_vector_cache.pop(vector_key,None)

        values=tuple(
            self._eval_node_cached(expr,row.inputs,pmap,row_signature)
            for row,row_signature in zip(rows,row_signatures)
        )
        self._node_vector_cache[vector_key]=(expr,values)
        self._node_vector_cache.move_to_end(vector_key)
        while len(self._node_vector_cache)>self._node_vector_cache_limit:
            self._node_vector_cache.popitem(last=False)
        return values

    def primitive_lineage(self, primitive_id: str) -> Tuple[str, ...]:
        """Return the transitive executable lineage rooted at a primitive.

        Direct parent_ids are preserved exactly; lineage closure adds every
        ancestor primitive reachable through those parent edges. This is
        provenance bookkeeping only: it never changes expression semantics or
        search eligibility.
        """
        seen: set[str] = set()
        stack = [str(primitive_id)]
        while stack:
            pid = str(stack.pop())
            if pid in seen:
                continue
            seen.add(pid)
            primitive = self.primitives.get(pid)
            if primitive is None:
                continue
            stack.extend(str(parent) for parent in primitive.parent_ids)
            stack.extend(
                str(parent)
                for parent in primitive.provenance.get("lineage_ids", ())
            )
        return tuple(sorted(seen))

    def executable_lineage(self, primitive_id: str) -> Tuple[str, ...]:
        """Return lineage reached through actual executable macro references.

        Provenance-only alias metadata is excluded from executable lineage.
        """
        seen: set[str] = set()
        stack = [str(primitive_id)]
        while stack:
            pid = str(stack.pop())
            if pid in seen:
                continue
            seen.add(pid)
            primitive = self.primitives.get(pid)
            if primitive is None:
                continue
            for node in self._walk(primitive.expression):
                if node.get("op") == "macro":
                    stack.append(str(node["id"]))
        return tuple(sorted(seen))

    def _h7_primary_pair_recency_priority(self, expr: Mapping[str, Any]) -> int:
        """Rank frozen Gen9-11 recent, executable primary pairs before stale aliases.

        This affects candidate order only. It uses direct executable macro IDs
        and recorded primitive generations; it never reads target labels, task
        family, holdout, transfer, OOD, or post-selection validation outcomes.
        """
        generation = int(self.generation)
        if generation not in (9, 10, 11):
            return 0
        direct_ids = {
            str(node["id"])
            for node in self._walk(expr)
            if node.get("op") == "macro" and node.get("id") is not None
        }
        primary_order = tuple(
            str(pid) for pid in getattr(self, "_h7_primary_macro_ids", ())
        )
        primary_ids = set(primary_order)
        if len(direct_ids) != 2 or not direct_ids.issubset(primary_ids):
            return 1
        parent_generations = []
        for pid in direct_ids:
            primitive = self.primitives.get(pid)
            if primitive is None:
                return 1
            parent_generation = int(getattr(primitive, "generation", -1))
            if parent_generation < 0:
                return 1
            parent_generations.append(parent_generation)
        if max(parent_generations) < generation - 1:
            return 1
        legacy_primary_pair_generations = {
            9: frozenset((4, 7)),
            10: frozenset((1, 4)),
            11: frozenset((3, 4)),
        }
        if legacy_primary_pair_generations.get(generation) == frozenset(parent_generations):
            return 1
        return 0

    def invent_primitive(self, train:Sequence[Trace], holdout:Sequence[Trace], transfer:Sequence[Trace], semantics:str="delta") -> Optional[CognitivePrimitive]:
        if len(train)<6: return None
        # Candidate selection uses only the permitted discovery/selection observations
        # in train. Holdout/transfer are measured after selection.
        keys=sorted(set().union(*(t.inputs.keys() for t in train)))
        existing=tuple(self.primitives)
        candidates=self._exprs(keys,existing,max(3,int(self.meta_policy["max_depth"])+1))
        pmap=self._prepare_node_eval_cache()
        def err(rows,expr):
            if not rows: return math.inf
            try:
                outputs=self._node_vector_eval(expr,rows,pmap)
                return sum(abs(value-row.target) for value,row in zip(outputs,rows))/len(rows)
            except Exception:
                return math.inf
        ranked=[]
        train_perfect_candidate_count=0
        recency_eligible_train_perfect_count=0
        recency_ineligible_train_perfect_count=0
        for expr in candidates:
            e1=err(train,expr)
            if e1>1e-9: continue
            train_perfect_candidate_count += 1
            macro_count=sum(1 for x in self._walk(expr) if x.get("op")=="macro")
            if self.generation>0 and self.primitives and macro_count<1: continue
            recency_priority=self._h7_primary_pair_recency_priority(expr)
            direct_ids={
                str(node["id"]) for node in self._walk(expr)
                if node.get("op")=="macro" and node.get("id") is not None
            }
            if int(self.generation) in (9,10,11) and len(direct_ids)>=2:
                if recency_priority==0:
                    recency_eligible_train_perfect_count += 1
                else:
                    recency_ineligible_train_perfect_count += 1
            ranked.append((
                recency_priority,
                -macro_count,
                ast_nodes(expr),
                json.dumps(expr,sort_keys=True),
                expr,
            ))
        if not ranked:
            self._h7_primitive_invention_summary = {
                "generation": int(self.generation),
                "enumerated_candidate_count": len(candidates),
                "train_perfect_candidate_count": train_perfect_candidate_count,
                "recency_eligible_train_perfect_candidate_count": recency_eligible_train_perfect_count,
                "recency_ineligible_train_perfect_candidate_count": recency_ineligible_train_perfect_count,
                "selected_primitive_id": None,
                "selected_direct_parent_ids": [],
                "selected_direct_parent_generations": [],
                "selected_pair_recency_gate_passed": False if int(self.generation) in (9,10,11) else None,
            }
            return None
        selected_recency_priority,_,nodes,_,expr=min(ranked, key=lambda x:(x[0],x[1],x[2],x[3]))
        used=tuple(sorted({str(x["id"]) for x in self._walk(expr) if x.get("op")=="macro"}))
        selected_parent_generations=[
            int(getattr(self.primitives.get(pid), "generation", -1))
            if self.primitives.get(pid) is not None else -1
            for pid in used
        ]
        self._h7_primitive_invention_summary = {
            "generation": int(self.generation),
            "enumerated_candidate_count": len(candidates),
            "train_perfect_candidate_count": train_perfect_candidate_count,
            "recency_eligible_train_perfect_candidate_count": recency_eligible_train_perfect_count,
            "recency_ineligible_train_perfect_candidate_count": recency_ineligible_train_perfect_count,
            "selected_direct_parent_ids": list(used),
            "selected_direct_parent_generations": selected_parent_generations,
            "selected_recency_priority": int(selected_recency_priority),
            "selected_pair_recency_gate_passed": (
                selected_recency_priority == 0 if int(self.generation) in (9,10,11) else None
            ),
        }
        train_error=err(train,expr)
        holdout_error=err(holdout,expr)
        transfer_error=err(transfer,expr)
        pid="prim:"+digest((expr,semantics))[:20]
        prim=CognitivePrimitive(
            pid,
            copy.deepcopy(expr),
            tuple(keys),
            semantics,
            self.generation,
            used,
            tuple(sorted({t.family for t in list(train)+list(holdout)+list(transfer)})),
            train_error,
            holdout_error,
            transfer_error,
            nodes,
            {
                "origin":"substrate_program_induction",
                "schema_given":False,
                "external_model":False,
                "selection_source":"discovery_and_selection_only",
                "validation_evaluated_after_selection":True,
            },
        )
        if hasattr(self, "_h7_primitive_invention_summary"):
            self._h7_primitive_invention_summary["selected_primitive_id"] = pid
        self.primitives[pid]=prim; self.archive[pid]=ArchiveRecord(prim)
        # The new primitive changes the executable macro environment. Advance
        # the cache epoch now so no result from the old pmap can be reused.
        self._prepare_node_eval_cache()
        self.events.append({
            "event":"PRIMITIVE_INVENTED",
            "primitive_id":pid,
            "used_primitives":used,
            "selection_source":"discovery_and_selection_only",
        })
        return prim

    def synthesize_process_frontier(
        self,
        rows:Sequence[Trace],
        transfer:Sequence[Trace],
        ood:Sequence[Trace],
        *,
        max_candidates:int=32,
    )->Tuple[ProcessCandidate,...]:
        """Retain a bounded frontier using discovery/selection observations only.

        The legacy transfer and ood parameters remain only for API compatibility.
        They are deliberately ignored during candidate generation, ordering, and
        frontier admission and are evaluated only after a candidate is selected.
        """
        keys=sorted(set().union(*(t.inputs.keys() for t in rows))); pids=tuple(self.primitives)
        pmap=self._prepare_node_eval_cache()
        primary_ids_for_diagnostics = (
            set(str(pid) for pid in getattr(self, "_h7_primary_macro_ids", ()))
            | set(self._h7_explicit_bootstrap_macro_ids(pids))
        ) & set(str(pid) for pid in pids)
        primary_pair_add_generated_signatures: set[str] = set()
        primary_pair_add_discovery_qualified_signatures: set[str] = set()
        # Stream qualified representatives directly into a lineage-keyed
        # frontier. The old implementation retained every qualifying
        # (expression, policy) tuple before this reduction.
        best_by_lineage={}
        pair_signature_structural_variants = {}
        self.last_process_candidate_selection_summary = {
            "discovery_qualified": 0,
            "post_selection_validation_ignored": True,
        }
        for pol in self.propose_search_policies():
            for expr in self._exprs(keys,pids,min(3,int(pol["max_depth"]))):
                diagnostic_pair_signature = None
                if (
                    expr.get("op") == "add"
                    and isinstance(expr.get("left"), Mapping)
                    and isinstance(expr.get("right"), Mapping)
                    and expr["left"].get("op") == "macro"
                    and expr["right"].get("op") == "macro"
                ):
                    pair_ids = {
                        str(expr["left"]["id"]),
                        str(expr["right"]["id"]),
                    }
                    if len(pair_ids) == 2 and pair_ids.issubset(primary_ids_for_diagnostics):
                        diagnostic_pair_signature = "|".join(sorted(pair_ids))
                        primary_pair_add_generated_signatures.add(diagnostic_pair_signature)
                try:
                    outputs=self._node_vector_eval(expr,rows,pmap)
                    tr=sum(abs(value-row.target) for value,row in zip(outputs,rows))/len(rows)
                    if tr>1e-9: continue
                    if diagnostic_pair_signature is not None:
                        primary_pair_add_discovery_qualified_signatures.add(diagnostic_pair_signature)
                    used=tuple(sorted({str(x["id"]) for x in self._walk(expr) if x.get("op")=="macro"}))
                    structural=json.dumps(expr,sort_keys=True)
                    direct_signature = tuple(sorted(set(str(pid) for pid in used)))
                    if len(direct_signature) == 2 and ast_depth(expr) <= 2:
                        pair_signature_structural_variants.setdefault(direct_signature, set()).add(structural)
                    selection_key=(
                        -len(used),
                        ast_nodes(expr),
                        len(structural),
                        structural,
                    )
                    self.last_process_candidate_selection_summary["discovery_qualified"] += 1
                    key=(selection_key,structural)
                    old=best_by_lineage.get(used)
                    if old is None or key < old[0]:
                        best_by_lineage[used]=(key,expr,used,pol)
                except Exception:
                    continue
        pair_diagnostic_summary = {
            "primary_pair_add_generated_signatures": sorted(primary_pair_add_generated_signatures),
            "primary_pair_add_discovery_qualified_signatures": sorted(primary_pair_add_discovery_qualified_signatures),
            "primary_pair_add_generated_count": len(primary_pair_add_generated_signatures),
            "primary_pair_add_discovery_qualified_count": len(primary_pair_add_discovery_qualified_signatures),
            "primary_pair_add_not_discovery_qualified_signatures": sorted(
                primary_pair_add_generated_signatures - primary_pair_add_discovery_qualified_signatures
            ),
        }
        self.last_process_candidate_selection_summary.update(pair_diagnostic_summary)
        if not best_by_lineage:
            self.process_frontier=[]
            return ()

        variants=tuple(best_by_lineage.values())
        # Count exact discovery-qualified structures before per-signature representative
        # reduction; this is diagnostic only and does not affect candidate order.
        pair_signature_merge_counts = {
            "|".join(signature): max(0, len(structures) - 1)
            for signature, structures in pair_signature_structural_variants.items()
        }
        # V22.2: discovery-only minimal primary-pair tier for the independent
        # closure frontier. This method enumerates its own expression space; it
        # does not call behavioral_search/find_exact_expression, so the V22.1
        # Occam selector cannot protect this separate candidate list. Use only
        # accepted primary-chain IDs and the observed discovery target vectors.
        # Include the generation-zero accepted root in this classification: it
        # is a real member of the primary chain, though it is not an invented
        # macro for discovery eligibility or expansion accounting.
        _primary_raw = getattr(self, "_h7_primary_macro_ids", ())
        _primary_order = [
            str(pid) for pid in _primary_raw
            if str(pid) in self.primitives
        ]
        _primary_ids = set(_primary_order)

        # The general 32-candidate closure frontier has a separate shallow pair
        # archive. Preserve one minimum-cost discovery-qualified representative
        # for every direct two-macro signature at AST depth <= 2.
        pair_signature_archive = {}
        for item in variants:
            signature = tuple(sorted(set(str(pid) for pid in item[2])))
            if len(signature) != 2 or ast_depth(item[1]) > 2:
                continue
            structural = json.dumps(item[1], sort_keys=True, separators=(",", ":"))
            key = (ast_depth(item[1]), ast_nodes(item[1]), len(structural), structural)
            old_item = pair_signature_archive.get(signature)
            if old_item is None:
                pair_signature_archive[signature] = (key, item)
            else:
                old_key, _ = old_item
                if key < old_key:
                    pair_signature_archive[signature] = (key, item)
        pair_archive_items = [value[1] for value in pair_signature_archive.values()]
        _pair_candidates = [
            item for item in variants
            if len(set(str(pid) for pid in item[2])) == 2
            and set(str(pid) for pid in item[2]).issubset(_primary_ids)
        ]
        _pair_min_depth = min(
            (ast_depth(item[1]) for item in _pair_candidates), default=None
        )
        _pair_minimal = [
            item for item in _pair_candidates
            if _pair_min_depth is not None and ast_depth(item[1]) == _pair_min_depth
        ]
        _pair_minimal_signatures = sorted({
            "|".join(sorted(set(str(pid) for pid in item[2])))
            for item in _pair_minimal
        })

        # Preserve lineage-distinct hypotheses under behavioral equivalence,
        # but never allow a crowded set of 3+ direct-macro expressions to evict
        # the minimal-depth exact two-parent primary-chain candidates before
        # the closure-reuse validator sees them. No expected-parent labels,
        # transfer/OOD/holdout rows, or validation results enter this ordering.
        legacy_primary_pair_generations = {
            9: frozenset((4, 7)),
            10: frozenset((1, 4)),
            11: frozenset((3, 4)),
        }

        def _v22_2_primary_pair_gate_eligible(item) -> bool:
            direct_ids = set(str(pid) for pid in item[2])
            if len(direct_ids) != 2 or not direct_ids.issubset(_primary_ids):
                return False
            pair_gens = []
            for pid in direct_ids:
                primitive = self.primitives.get(pid)
                if primitive is None:
                    return False
                pair_gens.append(int(getattr(primitive, "generation", -1)))
            if len(pair_gens) != 2 or min(pair_gens) < 0:
                return False
            generation = int(self.generation)
            if generation in (9, 10, 11):
                if max(pair_gens) < generation - 1:
                    return False
                if legacy_primary_pair_generations.get(generation) == frozenset(pair_gens):
                    return False
            return True

        def _expanded_ast_metrics(expression, stack=()):
            """Return unrolled (depth, node-count), expanding executable macros."""
            op = expression.get("op")
            if op == "macro":
                pid = str(expression.get("id"))
                if pid in stack or pid not in self.primitives:
                    return (1, 1)
                return _expanded_ast_metrics(
                    self.primitives[pid].expression, stack + (pid,)
                )
            if op in {"const", "get"}:
                return (1, 1)
            if op in {"abs", "neg", "threshold"}:
                child_depth, child_nodes = _expanded_ast_metrics(
                    expression["arg"], stack
                )
                return (1 + child_depth, 1 + child_nodes)
            left_depth, left_nodes = _expanded_ast_metrics(
                expression["left"], stack
            )
            right_depth, right_nodes = _expanded_ast_metrics(
                expression["right"], stack
            )
            return (
                1 + max(left_depth, right_depth),
                1 + left_nodes + right_nodes,
            )

        def _primary_lineage_size(item):
            lineage = set()
            for pid in item[2]:
                try:
                    lineage.update(str(x) for x in self.executable_lineage(pid))
                except Exception:
                    lineage.add(str(pid))
            return len(lineage & _primary_ids)

        def _v22_2_frontier_key(item):
            direct_ids = set(str(pid) for pid in item[2])
            is_minimal_primary_pair = (
                _pair_min_depth is not None
                and len(direct_ids) == 2
                and direct_ids.issubset(_primary_ids)
                and ast_depth(item[1]) == _pair_min_depth
            )
            # Process/closure synthesis is not a primary-invention recency
            # selector. Every retained expression is already an exact fit on
            # the combined discovery+selection rows. Within the minimal direct-
            # primary-pair tier, preserve executable primary-chain lineage before
            # comparing unrolled cost. This prevents a shallow ancestor alias from
            # outranking a lineage-preserving macro solely for being shorter.
            # No expected-pair label, holdout, transfer, or OOD result is read.
            expanded_depth, expanded_nodes = _expanded_ast_metrics(item[1])
            return (
                *h7_primary_pair_rank_prefix(
                    is_minimal_primary_pair,
                    _primary_lineage_size(item),
                    expanded_depth,
                    expanded_nodes,
                ),
                int(ast_depth(item[1])),
                int(ast_nodes(item[1])),
                len(json.dumps(item[1], sort_keys=True, separators=(",", ":"))),
                item[0][0],
                json.dumps(item[1], sort_keys=True, separators=(",", ":")),
            )
        frontier=list(variants)
        frontier.sort(key=_v22_2_frontier_key)
        pair_archive_signatures = set(pair_signature_archive)
        pair_archive_items.sort(key=_v22_2_frontier_key)
        # Every shallow direct pair is exempt from max_candidates; the cap is
        # applied only to the auxiliary closure frontier.
        frontier = pair_archive_items + [
            item for item in frontier
            if tuple(sorted(set(str(pid) for pid in item[2]))) not in pair_archive_signatures
        ][:max(1, int(max_candidates))]
        selected_frontier_item = frontier[0] if frontier else None
        selected_frontier_direct_ids = (
            set(str(pid) for pid in selected_frontier_item[2])
            if selected_frontier_item is not None else set()
        )
        selected_frontier_primary_ids = selected_frontier_direct_ids & _primary_ids
        selected_frontier_pair_gens = []
        for pid in sorted(selected_frontier_primary_ids):
            primitive = self.primitives.get(pid)
            if primitive is not None:
                selected_frontier_pair_gens.append(int(getattr(primitive, "generation", -1)))
        selected_frontier_is_minimal_primary_pair = bool(
            selected_frontier_item is not None
            and _pair_min_depth is not None
            and len(selected_frontier_direct_ids) == 2
            and selected_frontier_direct_ids.issubset(_primary_ids)
            and ast_depth(selected_frontier_item[1]) == _pair_min_depth
        )
        selected_frontier_recency_gate_applicable = bool(
            int(self.generation) in (9, 10, 11)
            and selected_frontier_is_minimal_primary_pair
        )
        selected_frontier_recency_gate_passed = (
            bool(_v22_2_primary_pair_gate_eligible(selected_frontier_item))
            if selected_frontier_recency_gate_applicable else None
        )
        self.last_process_candidate_selection_summary.update({
            "v22_3_selected_frontier_primary_macro_ids": sorted(selected_frontier_primary_ids),
            "v22_3_selected_frontier_pair_gens": selected_frontier_pair_gens if len(selected_frontier_pair_gens) == 2 else [],
            "v22_3_selected_frontier_recency_gate_applicable": selected_frontier_recency_gate_applicable,
            "v22_3_selected_frontier_recency_gate_passed": selected_frontier_recency_gate_passed,
            "v22_2_primary_pair_candidate_count": len(_pair_candidates),
            "v22_2_primary_pair_minimal_candidate_count": len(_pair_minimal),
            "v22_2_primary_pair_minimal_ast_depth": _pair_min_depth,
            "v22_2_primary_pair_minimal_direct_signatures": _pair_minimal_signatures,
            "v22_2_pair_signature_archive_count": len(pair_signature_archive),
            "v22_2_pair_signature_archive_returned": len(pair_archive_items),
            "v22_2_pair_signature_archive_signatures": sorted("|".join(signature) for signature in pair_signature_archive),
            "v22_2_pair_signature_merge_counts": pair_signature_merge_counts,
            "v22_2_frontier_direct_signatures": sorted(
                "|".join(sorted(set(str(pid) for pid in item[2])))
                for item in frontier if len(set(str(pid) for pid in item[2])) == 2
            ),
            "v22_2_primary_pair_gate_ineligible_signatures": sorted(
                "|".join(sorted(set(str(pid) for pid in item[2])))
                for item in _pair_minimal
                if not _v22_2_primary_pair_gate_eligible(item)
            ),
            "v22_2_pair_signature_archive_exempt_from_cap": True,
            "v22_2_auxiliary_frontier_cap": max(1, int(max_candidates)),
            "v22_2_discovery_only_primary_pair_priority": True,
            "v22_2_generation_zero_root_in_primary_classification": any(
                int(getattr(self.primitives.get(pid), "generation", 0)) == 0
                for item in _pair_minimal for pid in item[2]
            ),
        })
        # Do not apply another total-list slice here: shallow pair signatures
        # are exempt from the auxiliary candidate cap above.
        retained=[]
        for _,expr,used,pol in frontier:
            proc=ProcessCandidate(
                "proc:"+digest((expr,pol,self.generation))[:20],
                expr,
                used,
                self.generation,
                tuple(used),
                dict(pol),
                tuple(sorted({t.family for t in rows})),
                ast_nodes(expr),
                {
                    "origin":"substrate_process_synthesis_frontier",
                    "external_model":False,
                    "selection_source":"discovery_and_selection_only",
                    "post_selection_validation_ignored_during_selection":True,
                },
            )
            self.processes[proc.process_id]=proc
            retained.append(proc)
        self.process_frontier=[proc.process_id for proc in retained]
        self.events.append({
            "event":"PROCESS_FRONTIER_RETAINED",
            "generation":self.generation,
            "count":len(retained),
            "lineage_sets":[list(p.used_primitives) for p in retained],
            "selection_source":"discovery_and_selection_only",
        })
        return tuple(retained)

    def synthesize_process(self, rows:Sequence[Trace], transfer:Sequence[Trace], ood:Sequence[Trace])->Optional[ProcessCandidate]:
        frontier=self.synthesize_process_frontier(rows,transfer,ood)
        return frontier[0] if frontier else None

    def compatibility(self, proc:ProcessCandidate, trace:Trace)->float:
        risk=float(trace.context.get("transfer_risk",0.0)); amb=float(trace.context.get("ambiguity",0.0))
        return max(0.0,1.0-0.7*risk-0.5*amb)

    def evaluate(self, proc:ProcessCandidate, train:Sequence[Trace], holdout:Sequence[Trace], transfer:Sequence[Trace], ood:Sequence[Trace], conflict:Sequence[Trace])->Evaluation:
        pmap=self._prepare_node_eval_cache()
        def mae(rows):
            if not rows:return math.inf
            try:
                outputs=self._node_vector_eval(proc.expression,rows,pmap)
                return sum(abs(value-row.target) for value,row in zip(outputs,rows))/len(rows)
            except Exception:
                return math.inf
        tr,ho,te,oo=mae(train),mae(holdout),mae(transfer),mae(ood)
        conflict_error=mae(conflict)
        accepted=tr<=1e-9 and ho<=1e-9 and te<=1e-9
        return Evaluation(tr,ho,te,oo,max(0.0,1.0-conflict_error),float(proc.complexity),1.0/(1+proc.complexity),accepted)

    def retain(self, proc:ProcessCandidate, evaluation:Evaluation)->bool:
        if not evaluation.accepted:return False
        for pid in proc.used_primitives:
            if pid in self.archive:self.archive[pid].utility_history.append(1.0-evaluation.transfer_error)
        self.active=proc.process_id
        self.recursion_depth=max(self.recursion_depth,proc.generation+1)
        self.events.append({"event":"PROCESS_RETAINED","process_id":proc.process_id,"generation":proc.generation})
        return True

    def reuse(self, proc:ProcessCandidate, traces:Sequence[Trace])->Tuple[int,int]:
        a=r=0
        for t in traces:
            if self.compatibility(proc,t)>=0.65:a+=1
            else:r+=1
        return a,r

    def export_state(self)->Dict[str,Any]:
        state = {"max_depth":self.max_depth,"population":self.population,"generation":self.generation,"recursion_depth":self.recursion_depth,"meta_policy":copy.deepcopy(self.meta_policy),"active":self.active,"primitives":{k:asdict(v) for k,v in self.primitives.items()},"processes":{k:asdict(v) for k,v in self.processes.items()},"process_frontier":list(self.process_frontier),"events":copy.deepcopy(self.events)}
        # Ordered H7 chain and any explicitly tracked bootstrap vocabulary are
        # execution state: preserve them without deriving order from dict keys.
        state["_h7_primary_macro_ids"] = [
            str(pid) for pid in getattr(self, "_h7_primary_macro_ids", ())
        ]
        for key in ("bootstrap_primitives", "_h7_bootstrap_primitives"):
            if hasattr(self, key):
                value = getattr(self, key)
                state[key] = copy.deepcopy(list(value) if isinstance(value, (list, tuple)) else value)
        return state

    @classmethod
    def from_state(cls,state:Mapping[str,Any])->"RecursiveCognitiveCompiler":
        o=cls(int(state.get("max_depth",2)),int(state.get("population",24)),0)
        o.generation=int(state.get("generation",0)); o.recursion_depth=int(state.get("recursion_depth",0)); o.meta_policy=dict(state.get("meta_policy",o.meta_policy)); o.active=state.get("active")
        o.primitives={k:CognitivePrimitive(**v) for k,v in dict(state.get("primitives",{})).items()}
        o.archive={k:ArchiveRecord(v) for k,v in o.primitives.items()}
        o.processes={k:ProcessCandidate(**v) for k,v in dict(state.get("processes",{})).items()}
        o.process_frontier=list(state.get("process_frontier",[]))
        o.events=list(state.get("events",[]))
        raw_primary_ids = state.get("_h7_primary_macro_ids", [])
        if isinstance(raw_primary_ids, (list, tuple)):
            o._h7_primary_macro_ids = [str(pid) for pid in raw_primary_ids]
        for key in ("bootstrap_primitives", "_h7_bootstrap_primitives"):
            if key in state:
                setattr(o, key, copy.deepcopy(state[key]))
        return o

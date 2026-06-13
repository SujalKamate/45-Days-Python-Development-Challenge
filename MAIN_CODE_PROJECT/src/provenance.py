"""W3C PROV-O provenance tracking — entities, activities, agents, and derivations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
import json
import threading
import time


_UID = 0
def _next_id() -> str:
    global _UID
    _UID += 1
    return f'prov:{_UID:x}'


class ProvRecord:
    def __init__(self, prov_type: str, prov_id: str, **attrs: Any) -> None:
        self.prov_type = prov_type
        self.id = prov_id
        self.attrs = attrs
        self.time = time.time()

    def to_prov_json(self) -> Dict[str, Any]:
        entry: Dict[str, Any] = {'prov:type': self.prov_type}
        entry.update(self.attrs)
        return {self.id: entry}


class ProvEntity(ProvRecord):
    def __init__(self, prov_id: str, name: str = '', **attrs: Any) -> None:
        super().__init__('prov:Entity', prov_id, **attrs)
        self.attrs['prov:label'] = name or prov_id


class ProvActivity(ProvRecord):
    def __init__(self, prov_id: str, name: str = '', **attrs: Any) -> None:
        super().__init__('prov:Activity', prov_id, **attrs)
        self.attrs['prov:label'] = name or prov_id
        self.attrs['prov:startTime'] = time.time()


class ProvAgent(ProvRecord):
    def __init__(self, prov_id: str, name: str = '', **attrs: Any) -> None:
        super().__init__('prov:Agent', prov_id, **attrs)
        self.attrs['prov:label'] = name or prov_id


class ProvenanceGraph:
    """W3C PROV-O directed acyclic graph of entities, activities, agents, and derivations."""

    def __init__(self) -> None:
        self._entities: Dict[str, ProvEntity] = {}
        self._activities: Dict[str, ProvActivity] = {}
        self._agents: Dict[str, ProvAgent] = {}
        self._derivations: List[Tuple[str, str, str]] = []
        self._generations: List[Tuple[str, str, str]] = []
        self._associations: List[Tuple[str, str, str]] = []
        self._attrs: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def entity(self, prov_id: Optional[str] = None, name: str = '',
               **attrs: Any) -> str:
        eid = prov_id or _next_id()
        with self._lock:
            self._entities[eid] = ProvEntity(eid, name, **attrs)
        return eid

    def activity(self, prov_id: Optional[str] = None, name: str = '',
                 **attrs: Any) -> str:
        aid = prov_id or _next_id()
        with self._lock:
            self._activities[aid] = ProvActivity(aid, name, **attrs)
        return aid

    def agent(self, prov_id: Optional[str] = None, name: str = '',
              **attrs: Any) -> str:
        gid = prov_id or _next_id()
        with self._lock:
            self._agents[gid] = ProvAgent(gid, name, **attrs)
        return gid

    def derivation(self, derived: str, source: str,
                   activity_id: str = '') -> None:
        with self._lock:
            self._derivations.append((derived, source, activity_id))

    def generation(self, entity_id: str, activity_id: str) -> None:
        with self._lock:
            self._generations.append((entity_id, activity_id, ''))

    def association(self, activity_id: str, agent_id: str) -> None:
        with self._lock:
            self._associations.append((activity_id, agent_id, ''))

    def lineage(self, entity_id: str) -> List[Dict[str, Any]]:
        ancestors: List[Dict[str, Any]] = []
        visited: Set[str] = set()
        queue = [entity_id]
        while queue:
            eid = queue.pop(0)
            if eid in visited:
                continue
            visited.add(eid)
            ent = self._entities.get(eid)
            if ent:
                ancestors.append({'id': eid, 'type': 'entity',
                                  'name': ent.attrs.get('prov:label', eid)})
            for derived, source, _ in self._derivations:
                if derived == eid and source not in visited:
                    queue.append(source)
        return ancestors

    def to_prov_json(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            'prefix': {
                'prov': 'http://www.w3.org/ns/prov#',
                'xsd': 'http://www.w3.org/2001/XMLSchema#',
            },
            'entity': {},
            'activity': {},
            'agent': {},
        }
        with self._lock:
            for eid, ent in self._entities.items():
                result['entity'].update(ent.to_prov_json())
            for aid, act in self._activities.items():
                result['activity'].update(act.to_prov_json())
            for gid, ag in self._agents.items():
                result['agent'].update(ag.to_prov_json())

            for derived, source, act_id in self._derivations:
                rel = {'prov:type': 'prov:Derivation',
                       'prov:generatedEntity': derived,
                       'prov:usedEntity': source}
                if act_id:
                    rel['prov:activity'] = act_id
                result.setdefault('wasDerivedFrom', []).append(rel)

            for eid, aid, _ in self._generations:
                result.setdefault('wasGeneratedBy', []).append({
                    'prov:type': 'prov:Generation',
                    'prov:entity': eid,
                    'prov:activity': aid,
                })

            for aid, gid, _ in self._associations:
                result.setdefault('wasAssociatedWith', []).append({
                    'prov:type': 'prov:Association',
                    'prov:activity': aid,
                    'prov:agent': gid,
                })

        return result

    def export_json(self, path: str) -> None:
        import json as _json
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(self.to_prov_json(), f, indent=2)

    def clear(self) -> None:
        with self._lock:
            self._entities.clear()
            self._activities.clear()
            self._agents.clear()
            self._derivations.clear()
            self._generations.clear()
            self._associations.clear()

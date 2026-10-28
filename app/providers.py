"""Provider contracts. No mock generator or invented external API."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CreativeInput:
    project_id: str
    context: tuple[dict, ...]
    preferences: tuple[dict, ...]
    settings: dict


class GenerationProvider(Protocol):
    def estimate_cost(self, creative_input: CreativeInput, quantity: int) -> int | None: ...
    def generate(self, creative_input: CreativeInput, idempotency_key: str) -> str: ...


class PublishingProvider(Protocol):
    def publish(self, page_id: str, asset_path: str, caption: str, idempotency_key: str) -> str: ...
    def reconcile(self, idempotency_key: str) -> str | None: ...


INTEGRATIONS = [
    {"id": "muse", "name": "Muse AI", "status": "not_configured",
     "detail": "Serviço ainda não identificado. Importe o contexto em TXT, Markdown ou JSON. Nenhuma API foi presumida.",
     "capabilities": ["Importação local de contexto disponível"], "connected": False},
    {"id": "generation", "name": "Geração de imagens e vídeos", "status": "not_configured",
     "detail": "Aguardando seleção de provedor, credenciais e tabela de custos. Nenhuma geração paga está habilitada.",
     "capabilities": [], "connected": False},
    {"id": "meta", "name": "Facebook / Meta", "status": "not_configured",
     "detail": "OAuth e publicação pendentes. Requer aplicativo Meta, permissões de páginas e tokens no servidor.",
     "capabilities": [], "connected": False},
    {"id": "desktop", "name": "Agente de desktop", "status": "not_configured",
     "detail": "Executor local supervisionado disponível na área Automação do Desktop. Requer instalação no Windows e tarefas JSON; sem conexão remota ou adaptador Muse.",
     "capabilities": [], "connected": False},
]

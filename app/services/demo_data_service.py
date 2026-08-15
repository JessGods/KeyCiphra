"""Dados inteiramente fictícios para demonstrar organização e filtros."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from app.models.credential import Credential
from app.repositories.credential_repository import CredentialRepository
from app.services.category_service import CategoryService


@dataclass(frozen=True, slots=True)
class DemoCredentialTemplate:
    title: str
    username: str
    category: str
    path: str
    notes: str


@dataclass(frozen=True, slots=True)
class DemoDataResult:
    created_categories: int
    created_credentials: int


DEMO_CREDENTIALS = (
    DemoCredentialTemplate(
        "E-mail pessoal",
        "demo.pessoal@example.invalid",
        "Pessoal",
        "email-pessoal",
        "Conta fictícia usada para demonstrar uma credencial pessoal.",
    ),
    DemoCredentialTemplate(
        "Roteador de casa",
        "admin-demo",
        "Pessoal",
        "roteador-casa",
        "Equipamento fictício; estes dados não acessam um roteador real.",
    ),
    DemoCredentialTemplate(
        "Banco digital",
        "cliente-demo-1042",
        "Financeiro",
        "banco-digital",
        "Exemplo financeiro fictício sem vínculo com nenhuma instituição.",
    ),
    DemoCredentialTemplate(
        "Cartão de benefícios",
        "beneficio.demo@example.invalid",
        "Financeiro",
        "cartao-beneficios",
        "Cadastro inteiramente fictício para testar o filtro Financeiro.",
    ),
    DemoCredentialTemplate(
        "Portal da empresa",
        "colaborador.demo@example.invalid",
        "Trabalho",
        "portal-empresa",
        "Acesso corporativo fictício criado apenas para demonstração.",
    ),
    DemoCredentialTemplate(
        "VPN corporativa",
        "demo-vpn",
        "Trabalho",
        "vpn-corporativa",
        "Servidor e usuário fictícios; não representam uma empresa real.",
    ),
    DemoCredentialTemplate(
        "Repositório de código",
        "dev.demo@example.invalid",
        "Desenvolvimento",
        "repositorio-codigo",
        "Conta fictícia para demonstrar acessos de desenvolvimento.",
    ),
    DemoCredentialTemplate(
        "Servidor de testes",
        "deploy-demo",
        "Desenvolvimento",
        "servidor-testes",
        "Ambiente inexistente reservado exclusivamente para testes do KeyCiphra.",
    ),
    DemoCredentialTemplate(
        "Plataforma de cursos",
        "aluno.demo@example.invalid",
        "Estudos",
        "plataforma-cursos",
        "Matrícula e endereço fictícios para organização de estudos.",
    ),
    DemoCredentialTemplate(
        "Biblioteca digital",
        "leitor-demo-27",
        "Estudos",
        "biblioteca-digital",
        "Exemplo fictício de serviço educacional.",
    ),
    DemoCredentialTemplate(
        "Streaming de filmes",
        "familia.demo@example.invalid",
        "Entretenimento",
        "streaming-filmes",
        "Assinatura fictícia sem relação com um serviço comercial.",
    ),
    DemoCredentialTemplate(
        "Streaming de música",
        "ouvinte.demo@example.invalid",
        "Entretenimento",
        "streaming-musica",
        "Conta fictícia criada para preencher a categoria Entretenimento.",
    ),
    DemoCredentialTemplate(
        "Loja online",
        "comprador.demo@example.invalid",
        "Compras",
        "loja-online",
        "Cadastro de compra fictício; nenhuma transação pode ser realizada.",
    ),
    DemoCredentialTemplate(
        "Marketplace",
        "cliente-market-demo",
        "Compras",
        "marketplace",
        "Exemplo inteiramente fictício para testar buscas e categorias.",
    ),
    DemoCredentialTemplate(
        "Rede social de fotos",
        "perfil_demo_42",
        "Redes sociais",
        "rede-fotos",
        "Perfil fictício que não corresponde a uma pessoa real.",
    ),
    DemoCredentialTemplate(
        "Rede profissional",
        "profissional.demo@example.invalid",
        "Redes sociais",
        "rede-profissional",
        "Perfil profissional fictício para demonstração do cofre.",
    ),
    DemoCredentialTemplate(
        "Portal do convênio",
        "paciente-demo-731",
        "Saúde",
        "portal-convenio",
        "Não contém informações médicas nem dados de uma pessoa real.",
    ),
    DemoCredentialTemplate(
        "Laboratório de exames",
        "resultado.demo@example.invalid",
        "Saúde",
        "laboratorio-exames",
        "Acesso fictício criado somente para testar esta categoria.",
    ),
    DemoCredentialTemplate(
        "Companhia aérea",
        "viajante.demo@example.invalid",
        "Viagens",
        "companhia-aerea",
        "Programa de viagens fictício, sem reservas ou pontos reais.",
    ),
    DemoCredentialTemplate(
        "Reserva de hospedagem",
        "hospede-demo-55",
        "Viagens",
        "reserva-hospedagem",
        "Reserva inexistente usada para demonstrar o filtro Viagens.",
    ),
)


class DemoDataService:
    """Insere exemplos uma única vez e usa o fluxo criptografado normal."""

    def __init__(
        self,
        category_service: CategoryService,
        credential_repository: CredentialRepository,
    ) -> None:
        self._category_service = category_service
        self._credential_repository = credential_repository

    def populate(self) -> DemoDataResult:
        categories = {
            category.name.casefold(): category.name
            for category in self._category_service.list_all()
        }
        created_categories = 0
        for template in DEMO_CREDENTIALS:
            key = template.category.casefold()
            if key not in categories:
                created = self._category_service.create(template.category)
                categories[key] = created.name
                created_categories += 1

        existing_urls = {
            credential.url.strip().casefold()
            for credential in self._credential_repository.list_all()
        }
        created_credentials = 0
        for template in DEMO_CREDENTIALS:
            url = f"https://example.invalid/keyciphra-demo/{template.path}"
            if url.casefold() in existing_urls:
                continue
            self._credential_repository.add(
                Credential.create(
                    title=template.title,
                    username=template.username,
                    password=secrets.token_urlsafe(18),
                    url=url,
                    category=categories[template.category.casefold()],
                    notes=template.notes,
                )
            )
            existing_urls.add(url.casefold())
            created_credentials += 1
        return DemoDataResult(created_categories, created_credentials)

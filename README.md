
# Ação 413 — Painel de Dados para Atuação Resolutiva

MVP demonstrativo em Streamlit, com dados 100% sintéticos.

## O que contém

- Visão geral
- Território
- Temas
- Fluxo e tempo
- Universo 60+ / 80+
- Qualidade dos dados
- Camada conceitual de resolutividade
- Metodologia

## Modelo de dados

O protótipo separa:
- processos;
- vínculos pessoa–processo;
- vínculos assunto–processo;
- dimensão territorial.

Isso evita dupla contagem quando um processo tem várias pessoas ou vários assuntos.

## Executar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicar gratuitamente no Streamlit Community Cloud

1. Crie um repositório no GitHub.
2. Envie estes arquivos preservando a estrutura de pastas.
3. Acesse o Streamlit Community Cloud e escolha **Create app**.
4. Selecione o repositório, a branch e `app.py`.
5. Escolha um subdomínio disponível, por exemplo `acao413-mpap`.
6. Faça o deploy.

## Segurança

Este pacote contém somente dados sintéticos. Não substitua os CSVs por dados reais do Urano em hospedagem pública sem validação institucional de privacidade, segurança, governança e controle de acesso.

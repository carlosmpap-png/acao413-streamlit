# Ação 413 — Painel da Pessoa Idosa — MVP v0.3

Versão do protótipo que incorpora contexto demográfico oficial do IBGE para os 16 municípios do Amapá.

## O que mudou

- cadastro dos 16 municípios com código IBGE de 7 dígitos;
- integração automática com o SIDRA/IBGE;
- população 60+ e 80+ por município;
- composição 60+ por sexo;
- composição 60+ por cor ou raça;
- denominadores para taxas por 10 mil pessoas idosas;
- nova página **Contexto IBGE**;
- tabela territorial unindo numerador processual e denominador demográfico;
- documentação metodológica explícita.

## Fontes oficiais

- Censo Demográfico 2022 — SIDRA tabela 9514: população residente por sexo e idade.
- Censo Demográfico 2022 — SIDRA tabela 9606: população residente por cor ou raça, sexo e idade.
- Códigos territoriais: IBGE — Códigos dos Municípios.

## Segurança e interpretação

O MVP continua usando **dados processuais sintéticos**. O componente demográfico é oficial.
As taxas resultantes nesta fase são, portanto, **taxas demonstrativas**, úteis para validar a arquitetura,
e não indicadores reais de demanda do MP-AP.

Não inserir dados reais do Urano neste repositório público ou no Streamlit público sem validação institucional
de privacidade, segurança da informação, governança e controle de acesso.

## Executar localmente

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

## Atualização dos dados do IBGE

O app consulta o SIDRA automaticamente. Para guardar uma cópia bruta das consultas oficiais:

```powershell
py refresh_ibge.py
```

## Publicação

Aplicação demonstrativa: https://idosos.streamlit.app/

A branch `mvp-v03-ibge` deve ser revisada por Pull Request antes de ser incorporada à `main`.

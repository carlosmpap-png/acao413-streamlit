# Ação 413 — Painel da Pessoa Idosa — MVP v0.3

Protótipo em Streamlit da Ação 413, com integração de contexto demográfico oficial do IBGE para os 16 municípios do Amapá.

## Escopo desta versão

- dados processuais **100% sintéticos**, cobrindo 2022–2026;
- cobertura sintética dos 16 municípios do Amapá;
- chave territorial por código IBGE de 7 dígitos;
- população 60+, 60–79 e 80+ por município;
- composição 60+ por sexo e por cor ou raça;
- integração automática com o SIDRA/IBGE;
- página **Contexto IBGE**;
- razão demonstrativa de demandas por 10 mil pessoas idosas;
- controles de qualidade, metodologia e ressalvas de interpretação.

## Fontes oficiais

- Censo Demográfico 2022 — SIDRA tabela 9514: população residente por sexo e idade;
- Censo Demográfico 2022 — SIDRA tabela 9606: população residente por cor ou raça, sexo e idade;
- variável SIDRA **93 — População residente (Pessoas)**;
- códigos territoriais oficiais do IBGE.

## Regra territorial

A integração é feita pelo **código IBGE**, e não pelo nome textual do município. O nome serve somente para exibição.

## Indicador territorial do MVP

A versão 0.3 apresenta uma **razão demonstrativa de demandas por 10 mil pessoas idosas no período**:

```
processos distintos que atendem aos filtros
------------------------------------------------  × 10.000
população da faixa etária no Censo 2022
```

O denominador acompanha o filtro etário:

- **60+** → população 60+;
- **60–79** → população 60+ menos população 80+;
- **80+** → população 80+.

O indicador é uma razão acumulada para o período selecionado. Não deve ser interpretado como incidência anual.

## Segurança e interpretação

O componente demográfico é oficial; o componente processual permanece sintético.

Nenhum dado real do Urano deve ser colocado neste repositório público ou no Streamlit público sem validação institucional de privacidade, segurança da informação, governança e controle de acesso.

As razões exibidas nesta fase servem para validar a arquitetura analítica e **não representam demanda real do MP-AP**.

## Testes

A branch possui testes automatizados para:

- identificação exata das dimensões da API SIDRA;
- preservação do código IBGE;
- cálculo dos denominadores 60+, 60–79 e 80+;
- seleção do universo processual por faixa etária;
- cálculo da razão por 10 mil;
- cobertura sintética 2022–2026 e dos 16 municípios.

O GitHub Actions executa compilação e `pytest` em pushes e pull requests.

## Executar localmente

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

## Snapshot opcional do SIDRA

O app consulta o SIDRA automaticamente. Para guardar uma cópia bruta das consultas oficiais:

```powershell
py refresh_ibge.py
```

Os arquivos serão gravados em `data/`, usando a variável 93 (População residente).

## Publicação

Aplicação demonstrativa: https://idosos.streamlit.app/

A branch `mvp-v03-ibge` deve ser revisada no Pull Request antes de ser incorporada à `main`.

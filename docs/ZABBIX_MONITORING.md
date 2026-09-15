# 📊 Monitoramento Zabbix — Radar Jarbis

Este documento descreve como configurar o monitoramento no Zabbix utilizando os endpoints de métricas nativos dos bots do Radar Jarbis (Amazon e Mercado Livre).

---

## 🎯 Estrutura do Host `RADAR-DO-JARBIS` (Grupo: `RADAR-JARBIS`)

O host `RADAR-DO-JARBIS` (pertencente ao grupo de hosts `RADAR-JARBIS`) é dedicado exclusivamente às **métricas de aplicação e de negócio**. Os recursos de sistema operacional (CPU geral da VM, disco, rede) devem ficar em um host separado (ex: com Template Linux by Zabbix agent).

```mermaid
flowchart TD
    subgraph GCP["Google Cloud Platform (VMs)"]
        VM1["VM Amazon\n(Porta 8000/metrics.json)"]
        VM2["VM Mercado Livre\n(Porta 8001/metrics.json)"]
    end

    subgraph Zabbix["Rede Local / Zabbix Server & Proxy"]
        HostJarbis["Host: RADAR-DO-JARBIS\n(Grupo: RADAR-JARBIS)"]
        
        MasterAmazon["Item Mestre: radar.amazon.metrics.json\nhttp://{$AMAZON_HOST}:{$AMAZON_PORT}/metrics.json"]
        MasterMeli["Item Mestre: radar.meli.metrics.json\nhttp://{$MELI_HOST}:{$MELI_PORT}/metrics.json"]
        
        HostJarbis --> MasterAmazon
        HostJarbis --> MasterMeli
    end

    MasterAmazon -->|HTTP GET :8000 (Firewall Restrito)| VM1
    MasterMeli -->|HTTP GET :8001 (Firewall Restrito)| VM2
```

---

## 🚀 Endpoints Disponíveis nos Bots

Cada bot expõe duas interfaces na sua respectiva porta HTTP (`8000` para Amazon e `8001` para Meli):
1. **`/metrics.json` (Recomendado para Zabbix)**: Retorna um payload JSON limpo com os contadores de negócio e sistema para extração via **JSONPath**.
2. **`/metrics`**: Retorna o formato tradicional de texto do Prometheus (*Prometheus exposition format*).

---

## 🚀 Como Importar o Host Diretamente no Zabbix

1. Baixe ou copie o arquivo [`docs/zabbix_host_radar_jarbis.yaml`](file:///home/robson/projetos/radar-jarbis/docs/zabbix_host_radar_jarbis.yaml).
2. No painel Web do Zabbix, vá em:
   - **Data collection** (ou **Configuration**) ➡️ **Hosts**
   - Clique no botão **Import** (canto superior direito)
   - Selecione o arquivo `docs/zabbix_host_radar_jarbis.yaml`
   - Marque as opções de atualização e clique em **Import**.
3. No host `RADAR-DO-JARBIS`, as macros já virão preenchidas ou podem ser ajustadas.

---

## 📋 Lista de Itens Criados

### 1. Bot Amazon
- **Item Mestre**: `Amazon - Raw JSON Metrics` (`radar.amazon.metrics.json`, HTTP Agent em `http://{$AMAZON_HOST}:{$AMAZON_PORT}/metrics.json`)
- **Itens Dependentes (JSONPath)**:
  - `radar.amazon.messages_received` (`$.messages_received`) ➡️ Mensagens recebidas dos canais de entrada.
  - `radar.amazon.offers_published` (`$.offers_published`) ➡️ Ofertas validadas e postadas no canal de saída.
  - `radar.amazon.offers_filtered` (`$.offers_filtered`) ➡️ Ofertas descartadas por regras de filtros/desconto.
  - `radar.amazon.errors_total` (`$.errors_total`) ➡️ Quantidade total de erros e exceções capturadas.
  - `radar.amazon.reconnect_attempts` (`$.reconnect_attempts`) ➡️ Tentativas de reconexão do MTProto.
  - `radar.amazon.memory_rss` (`$.memory_rss_bytes`) ➡️ Consumo real de memória RAM do processo (Bytes).

### 2. Bot Mercado Livre
- **Item Mestre**: `Mercado Livre - Raw JSON Metrics` (`radar.meli.metrics.json`, HTTP Agent em `http://{$MELI_HOST}:{$MELI_PORT}/metrics.json`)
- **Itens Dependentes (JSONPath)**:
  - `radar.meli.messages_received` (`$.messages_received`) ➡️ Mensagens recebidas dos canais Meli.
  - `radar.meli.offers_published` (`$.offers_published`) ➡️ Ofertas Meli convertidas e publicadas.
  - `radar.meli.offers_filtered` (`$.offers_filtered`) ➡️ Ofertas descartadas por regras de filtros.
  - `radar.meli.memory_rss` (`$.memory_rss_bytes`) ➡️ Consumo real de memória RAM do processo (Bytes).

---

## 🏷️ Macros do Host `RADAR-DO-JARBIS`

| Macro | Valor Padrão | Descrição |
| :--- | :--- | :--- |
| `{$AMAZON_HOST}` | `35.226.101.128` | IP público ou DNS da VM Amazon no GCP |
| `{$AMAZON_PORT}` | `8000` | Porta de métricas do bot Amazon |
| `{$MELI_HOST}` | `34.10.13.28` | IP público ou DNS da VM Mercado Livre no GCP |
| `{$MELI_PORT}` | `8001` | Porta de métricas do bot Mercado Livre |

---

## 🚨 Triggers de Alerta

- **`Radar Jarbis - Bot Amazon Indisponível`**: Dispara se o endpoint `http://{$AMAZON_HOST}:{$AMAZON_PORT}/metrics.json` parar de responder por mais de 3 minutos.
- **`Radar Jarbis - Bot Mercado Livre Indisponível`**: Dispara se o endpoint `http://{$MELI_HOST}:{$MELI_PORT}/metrics.json` parar de responder por mais de 3 minutos.

---

## 🔄 Ponto de Restauração / Rollback

Consulte [`docs/ROLLBACK_MONITORING.md`](file:///home/robson/projetos/radar-jarbis/docs/ROLLBACK_MONITORING.md) para detalhes de reversão ao formato anterior Prometheus text-only caso necessário.

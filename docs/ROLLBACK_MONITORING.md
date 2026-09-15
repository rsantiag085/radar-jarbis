# Procedimento de Rollback — Monitoramento Radar Jarbis

Este documento descreve as etapas para reverter as alterações de monitoramento caso você deseje retornar ao estado anterior (Prometheus text-only).

---

## Ponto de Restauração Criado

- **Git Tag**: `backup-before-json-metrics`
- **Git Branch**: `backup-before-json-metrics`
- **Arquivo de Template Anterior**: `docs/zabbix_host_radar_jarbis.yaml` (versão Prometheus puro)

---

## Passos para Rollback

### 1. Reverter o Código Python para o Ponto de Restauração
```bash
git checkout backup-before-json-metrics
```

### 2. Reiniciar os Serviços nas VMs do GCP
**VM Amazon:**
```bash
sudo systemctl restart radar-jarbis.service
```

**VM Mercado Livre:**
```bash
sudo systemctl restart radar-jarbis-meli.service
```

### 3. Reverter os Itens no Zabbix
Caso tenha alterado as chaves e pré-processamentos para JSONPath no Zabbix e queira voltar ao Prometheus Pattern anterior:
1. Acesse o Zabbix Web.
2. Importe o template/host original a partir de `docs/zabbix_host_radar_jarbis.yaml`.
3. Ou execute o script de reversão automática via API.

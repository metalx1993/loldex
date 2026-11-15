# Fase 10 — qualità e governance

Avvio: 15 novembre 2026. La consegna implementa strumenti e procedure; la loro
verifica è registrata in [phase10-delivery.md](phase10-delivery.md). Il ciclo
programmato reale GitHub → SiteGround resta un criterio operativo aperto, non
sostituibile dai test sintetici. CORE/D1 e le decisioni congelate restano invariati.

## Attività e criteri

| Attività | Implementazione | Accettazione |
|---|---|---|
| 10.1 Baseline riproducibile | `scripts.quality_report`: validatori esistenti di schema/tassonomie/layer e generazione condivisa, confronto esatto di tutti i dati generati, OpenAPI, licenza, manifest e shard; rilevamento input ambigui e modifiche durante il controllo | Corpus reale, fixture valide e negative; zero scritture su corpus/site; conteggio e fingerprint degli input, inventario/hash degli output; esiti in phase10-delivery.md |
| 10.2 Revisione e correzione | Procedure, ruoli, registro decisioni, esempi sufficienti/insufficienti, template issue/PR e CONTRIBUTING aggiornato | La decisione umana resta esplicita; upstream, interpretazioni e proiezioni si correggono nel proprio layer; tassonomie/identità/compatibilità richiedono revisione dedicata |
| 10.3 Gestione operativa | Verificatore offline di coerenza delle prove, casi con/senza variazioni, gestione di errori/prove mancanti, procedure di diagnosi e recupero A2 | Strumento verificato con fixture sintetiche; **accettazione del ciclo reale ancora aperta** fino all'evento GitHub schedule, gate riusciti, snapshot correlato, pubblicazione host programmata e riscontro HTTPS |
| 10.4 Regressioni semantiche | Casi avversari indipendenti permanenti, regressioni per i problemi riprodotti, gate di qualità nel workflow prima dei test e della pubblicazione | Risultati della suite e della revisione indipendente in phase10-delivery.md; nessuna promozione di confidence, fusione distruttiva o inferenza di freschezza |

## Comandi e ambiti

```sh
python3 -m scripts.quality_report > work/quality-report.json
python3 -m scripts.check_operational_cycle work/automatic-cycle-evidence.json
```

Il primo comando ricostruisce in memoria tramite `scripts.build_all.complete_artifacts`
e confronta i byte con il sito locale, riutilizzando i controlli di `scripts.validate`.
Non invoca lo scrittore del sito. Un eventuale stato CORE deve essere quello usato
per la build, indicato con `--state`. Le tassonomie non dipendono da assert
rimovibili con `python -O`. I parser stretti già presenti vengono riutilizzati
per rifiutare chiavi duplicate, senza cambiare la semantica normativa dei loader
CORE. Hash e inventario degli input sono ricontrollati a fine esecuzione; non c'è
un lock e le modifiche concorrenti ABA non possono essere escluse. I file
runtime/UI scritti a mano non rientrano nel confronto dei dati generati.

Il secondo comando verifica soltanto la coerenza delle prove fornite: non ne
autentica l'origine. Record originali API/log/Git/Site Tools/HTTPS devono essere
conservati e revisionati indipendentemente. `PENDING` non è un successo. Una
chiamata manuale non dimostra un avvio programmato; i test sintetici non sono
prove di produzione. Contraddizioni già note vengono rifiutate anche quando
altre sezioni mancano. Contratti e codici d'uscita sono in
[operations-governance.md](operations-governance.md).

## Regole e manutenzione

Usare [quality-governance.md](quality-governance.md) per triage, correzioni,
revisioni e decisioni. Metriche descrittive e campi facoltativi mancanti non
vengono convertiti in errori contrattuali o arricchimenti inventati. D2 health
non è freschezza CORE; provenance e confidence appartengono ai claim, non a un
intero record. Candidati di identità e alias mantengono i contratti della fase 9.

Gli strumenti non acquisiscono sorgenti, non correggono automaticamente i dati,
non pubblicano, non inviano notifiche e non cambiano pianificazioni. Il workflow
esistente esegue il rapporto come gate aggiuntivo dopo la build, mantenendo
pianificazione settimanale e protezione unchanged-base. Non viene introdotto un
nuovo servizio automatico.

La qualità/governance continua dopo la consegna. Non dichiarare la fase
operativamente accettata finché il criterio reale 10.3 resta aperto. Il controllo
del 15 novembre è in [cron-check-2026-11-15.json](cron-check-2026-11-15.json):
SiteGround ha pubblicato il commit disponibile, ma nessun evento schedule GitHub
è stato osservato; prossimo orario configurato 16 novembre, 05:00 Europe/Rome,
senza garanzia di avvio puntuale.

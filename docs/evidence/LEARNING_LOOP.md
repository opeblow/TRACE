# Learning-loop evidence (Walrus Memory, Mainnet)

> **Controlled test scenario.** The operator acted as the user and entered labels and feedback about a real, public Mainnet wallet.
> Chain data (Tatum Sui gRPC) and memory writes (Walrus Memory relayer) are real. Only jobs Walrus reported as completed are counted.
> Regenerate with `python apps/api/scripts/memory_demo.py`.

Generated 2026-10-30T11:12:10Z · Sui mainnet checkpoint 339756201 · wallet [`0x7d3fe5…f9cf72`](https://suiscan.xyz/mainnet/account/0x7d3fe51822d20ea780d061e17bcb7204a645ceef278b562db1ddfe5b35f9cf72) · workspace ref `11eba7351b`

## PRD acceptance checks

- [x] at least 10 completed mainnet writes
- [x] later session recalled memory
- [x] memory changed user visible result
- [x] stateless output shown for comparison
- [x] other workspace isolated

## Memory writes (12 completed of 12 attempted)

| Type | Purpose | Status | Seconds to complete | Walrus blob |
|---|---|---|---|---|
| counterparty_label | Label for counterparty in 2 finding(s) | succeeded | 38.3 | [`gjr6YrzEN4Qy…`](https://walruscan.com/mainnet/blob/gjr6YrzEN4QyWn4QS28y6FDsdjmdcc9g8awxGJV-TwY) |
| counterparty_label | Label for counterparty in 1 finding(s) | succeeded | 37.4 | [`cUuSPWXXdUgX…`](https://walruscan.com/mainnet/blob/cUuSPWXXdUgX23yquSVdzLTKLmNOXnmkwFOs20FueO0) |
| counterparty_label | Label for counterparty in 1 finding(s) | succeeded | 36.7 | [`WchJkwyCUIDS…`](https://walruscan.com/mainnet/blob/WchJkwyCUIDS2laZluaMTd-ZkWY44scxt7BrvypU3Bw) |
| alert_feedback | Feedback on high finding 3bLCescaqu… | succeeded | 35.8 | [`95NQQ97x_4XG…`](https://walruscan.com/mainnet/blob/95NQQ97x_4XGUPCl3NsqwQOCPqnyvjXRpEyWsRoCblM) |
| alert_feedback | Feedback on high finding HypmoNTcnn… | succeeded | 35.1 | [`V-tz0F7yXYOc…`](https://walruscan.com/mainnet/blob/V-tz0F7yXYOcScfheLO4UJ1Btkdp6-du2R8VCMhx1x0) |
| alert_feedback | Feedback on high finding GjhxYeztxs… | succeeded | 34.3 | [`EFCgZte7tvdg…`](https://walruscan.com/mainnet/blob/EFCgZte7tvdgHmMvxa2QCYJCgtGCmUYwkDhmp5sBmMs) |
| alert_feedback | Feedback on high finding HRFe4D2AM1… | succeeded | 33.4 | [`0K5UCru8iynN…`](https://walruscan.com/mainnet/blob/0K5UCru8iynNiJGivPZ_bipZPc0_4ujo7WQPxG4px0o) |
| alert_feedback | Feedback on high finding 2axSjTwAcT… | succeeded | 32.6 | [`pteCurzQs25K…`](https://walruscan.com/mainnet/blob/pteCurzQs25K3iO2CKk86hKRFo6mUaVdPy4IWpONP9A) |
| alert_feedback | Feedback on high finding G4v9WCCvkK… | succeeded | 31.4 | [`iwpuAKpI0Q_J…`](https://walruscan.com/mainnet/blob/iwpuAKpI0Q_JqhTYqtUpPMGlsR3t3WwK79qfVQzuek8) |
| alert_feedback | Feedback on high finding AtesQk9PaQ… | succeeded | 30.3 | [`bTBELtvh-NRy…`](https://walruscan.com/mainnet/blob/bTBELtvh-NRysdKRz-q3cucu0HaJM7z7mU7ZCNRGNes) |
| alert_feedback | Feedback on high finding DEbgL7QQMC… | succeeded | 29.2 | [`B_aO_Ca4lZfk…`](https://walruscan.com/mainnet/blob/B_aO_Ca4lZfkVK8gDrirxiqXNADxzhoywKAoYTewB9M) |
| investigation_summary | Investigation summary from the first analysis | succeeded | 28.5 | [`A2i-I6cL07YD…`](https://walruscan.com/mainnet/blob/A2i-I6cL07YDexVBsMryzojHqfsU7exkVToLOH-e1rY) |

## Same wallet, new session: without memory vs. with recalled memory

Session 1 (no memories): **none**, 10 findings.
Session 2 (fresh API client): memory **used**, 12 recalled, result changed: **True**.
A different workspace analysing the same wallet recalled **0** memories.

| Transaction | SUI | Counterparty | Without memory | With memory | Review state |
|---|---|---|---|---|---|
| [`3bLCescaqu…`](https://suiscan.xyz/mainnet/tx/3bLCescaqu9JAKm5YzKoAVr3tDQ2WKdptPNEk5p4u9Mi) | 16516.159733664 | 0xbe04f5…ba5369 | high | **low** | marked_expected |
| [`HypmoNTcnn…`](https://suiscan.xyz/mainnet/tx/HypmoNTcnnaVJkitAgWFGwoypiyyNPAJrME5teKXs2fz) | 16510.622593254 | — | high | **high** | needs_review |
| [`GjhxYeztxs…`](https://suiscan.xyz/mainnet/tx/GjhxYeztxsxtWp6PqLM8wMWY9yp9JvaxYzRvMXS61MfC) | 4085.438849406 | — | high | **high** | needs_review |
| [`HRFe4D2AM1…`](https://suiscan.xyz/mainnet/tx/HRFe4D2AM1Mv3maqPXjCiQFSqSFvKM97bdB5qLXwndqQ) | 4084.999112296 | 0xbe04f5…ba5369 | high | **low** | marked_expected |
| [`2axSjTwAcT…`](https://suiscan.xyz/mainnet/tx/2axSjTwAcT84nnR5ce7imPawwRkpreXYc4VMjTPpKcz8) | 5.001088099 | 0x20f86f…1ccd5d | high | **low** | marked_expected |
| [`G4v9WCCvkK…`](https://suiscan.xyz/mainnet/tx/G4v9WCCvkKDv4k89rgHfpeme6qi77XZxg2cCk4kzdbuD) | 5 | 0xdbf54a…93fac5 | high | **low** | marked_expected |
| [`AtesQk9PaQ…`](https://suiscan.xyz/mainnet/tx/AtesQk9PaQkinDB9XD8gvJosMCxwnk6vJh7vkeJmaktq) | 3.001423637 | — | high | **high** | needs_review |
| [`DEbgL7QQMC…`](https://suiscan.xyz/mainnet/tx/DEbgL7QQMC1XkdpAaqvGtbiMH67dnGbo2E1SLtesMbUj) | 0.192388963 | — | high | **high** | needs_review |
| [`6KTz2FwjLL…`](https://suiscan.xyz/mainnet/tx/6KTz2FwjLLCKPnDTuajwR9n49Whxh178jsX56zcCRBX) | 0.163500262 | — | high | **high** | open |
| [`2cbhSyj3by…`](https://suiscan.xyz/mainnet/tx/2cbhSyj3bypkpPLWrBRMs2fQjzjQJJ7dDXx7RZscfLt8) | 0.015578692 | — | medium | **medium** | open |

Every changed row cites the Walrus blob IDs that caused it (see `walrus-memory-evidence.json`). Labels and feedback are user assertions:
TRACE lowers priority but never hides a finding or treats memory as proof of safety.

# fr-dpia — full reference

## Answers file

One `key: value` per line. A line starting with `#` is a comment, and so is anything after
` #` on a line. The first occurrence of a key wins. CRLF files read the same as LF files.
`bash scripts/fr-dpia.sh init` prints every key with its question.

| Keys | Value | Empty or `unknown` becomes |
|---|---|---|
| `c1` … `c9` | `yes \| <fact>`, `no \| <why>`, `unknown` (`oui` / `non` accepted) | `[unknown]` with a TODO question |
| `l1` … `l14` | same | counted as an unknown list item |
| `title`, `controller`, `dpo`, `purposes`, `benefits`, `standards`, `processors`, `data_subjects`, `data`, `recipients`, `retention`, `lifecycle`, `supports`, `legal_basis`, `minimisation`, `accuracy`, `information`, `consent`, `access_portability`, `rectification_erasure`, `restriction_objection`, `transfers`, `measures_data`, `measures_system`, `measures_org`, `subjects_views` | free text | `TODO: <the question>` |
| `<risk>_impacts`, `_sources`, `_threats`, `_measures`, for `access`, `modification`, `disappearance` | free text | `TODO: <the question>` |
| `<risk>_severity`, `<risk>_likelihood` | `1`–`4` or a CNIL label (`négligeable`, `limitée`, `importante`, `maximale`, and the masculine forms) | `TODO` |

Anything else in a criterion, list item or scale field stops the script with exit code 2.

## Criteria

The nine criteria of the EDPB-endorsed WP248 rev.01 guidelines, numbered as WP248 numbers
them. The CNIL lists the same nine in deliberation 2018-326, in another order.

| # | WP248 | CNIL wording (deliberation 2018-326) |
|---|---|---|
| 1 | Evaluation or scoring, including profiling and predicting | évaluation/scoring (y compris le profilage) |
| 2 | Automated decision-making with legal or similar significant effect | prise de décision automatisée avec un effet juridique ou similaire |
| 3 | Systematic monitoring | surveillance systématique de personnes |
| 4 | Sensitive data or data of a highly personal nature | données sensibles |
| 5 | Data processed on a large scale | données traitées à grande échelle |
| 6 | Matching or combining datasets | croisement ou combinaison de données |
| 7 | Data concerning vulnerable data subjects (children, employees, patients…) | données concernant des personnes vulnérables |
| 8 | Innovative use or new technological or organisational solutions | utilisation innovante ou application de nouvelles solutions technologiques ou organisationnelles |
| 9 | Processing that prevents exercising a right or using a service or contract | traitement pouvant exclure du bénéfice d'un droit, d'un service ou d'un contrat |

## CNIL list (deliberation 2018-327)

`l1` … `l14` are the fourteen rows of the annex, in order, quoted in the script and in the
`init` output. The CNIL states the list is not exhaustive ("Cette liste a un caractère
non-exhaustif"): a processing off the list can still need a DPIA.

## Verdict

Evaluated top to bottom, first match wins:

| Verdict | When |
|---|---|
| `DPIA required` | at least one CNIL list item is `yes` |
| `DPIA likely` | two or more criteria are `yes` |
| `DPIA undetermined` | fewer than two `yes`, but `yes` + `unknown` criteria reach two, or a list item is `unknown` |
| `DPIA not indicated` | none of the above; with exactly one criterion met, the `Reason:` line recalls that WP248 says one criterion can be enough in some cases |

Every `Verdict:` line ends with `to confirm with the DPO` (`answer the unknowns, then confirm
with the DPO` for `undetermined`). "Likely" is the WP248 wording ("in most cases … two
criteria would require a DPIA"); deliberation 2018-326 is firmer ("doit faire l'objet d'une
AIPD"). The script does not read the CNIL exemption list; a DPO who knows one applies
overrides the verdict.

## Scales

From *PIA, les bases de connaissances* (CNIL, February 2018), sections 1.4 and 1.5. Both are
estimated with the existing or planned measures taken into account.

| Level | Severity (gravité) | Likelihood (vraisemblance) |
|---|---|---|
| 1 | Négligeable — no impact, or inconveniences overcome without difficulty | Négligeable — the risk sources do not seem able to carry out the threat |
| 2 | Limitée — significant inconveniences, overcome despite a few difficulties | Limité — it seems difficult for the risk sources |
| 3 | Importante — significant consequences, they should overcome, but with real and significant difficulties | Important — it seems possible for the risk sources |
| 4 | Maximale — significant, or even irreversible, consequences they may not overcome | Maximal — it seems extremely easy for the risk sources |

## Map position, not a risk level

The CNIL method asks for a map of residual risks by severity and likelihood (*PIA, la
méthode*, 4.1; the template in *PIA, les modèles* is a 4×4 grid). It publishes no formula
turning the pair into a level, so the script does not invent one. It prints the position
`G<severity>/V<likelihood>` and one flag:

`wp248-high-residual-example: yes` when severity is 4 or likelihood is 4. WP248 gives as an
example of an unacceptable high residual risk consequences "which they may not overcome"
(the wording of severity 4) "and/or when it seems obvious that the risk will occur" (the
shape of likelihood 4). `unknown` when either value is unknown, `no` otherwise. The flag
only frames the art. 36 question; it does not answer it.

## Prior consultation (art. 36)

Section 5 of the draft always ends with a **Question for the DPO**, never a conclusion:
whether a residual risk remains high once the action plan is in place, so that the CNIL must
be consulted before the processing starts. When a value is unknown, it says the question
cannot be assessed yet.

## `render --out` summary

`render <answers-file> --out <draft.md>` writes the draft to `<draft.md>`, creating its
directory, and prints in order: `Draft written to: <draft.md>`, the check block,
`Prior consultation (art. 36): <the section 5 question>`, then `TODO questions` with one
`- <key>: <question>` line per text, severity or likelihood key still empty or `unknown`
(each key once; unknown criteria are already in the check block).
The DPO advice and the controller's decision are not keys: they stay TODO in section 6 only.

## Draft structure

`render` follows *PIA, la méthode* (CNIL, February 2018): 0 the requirement check;
1 context (overview; data, processes and supports); 2 fundamental principles (2.1 necessity
and proportionality, 2.2 rights of data subjects); 3 risks (3.1 existing or planned measures,
3.2 one block per feared event: impacts, sources, threats, measures, severity, likelihood);
4 action plan with the CNIL plan scales (term: Trimestre / Année / 3 ans; difficulty: Faible /
Moyenne / Élevée; cost: Nul / Moyen / Important; progress: Non démarré / En cours / Terminé);
5 residual risks and the art. 36 question; 6 validation left open (DPO advice under art.
35(2), data subjects' views under art. 35(9), the controller's decision, the review at least
every three years from deliberation 2018-326).

## Sources

Each was read on its official page on 2026-11-19.

| Source | URL | Used for |
|---|---|---|
| CNIL deliberation 2018-327 (Légifrance) | <https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000037559521> | the fourteen list items, "non-exhaustif" |
| CNIL deliberation 2018-326 (Légifrance) | <https://www.legifrance.gouv.fr/jorf/article_jo/JORFARTI000037559519> | the nine criteria in French, "au moins deux des critères", review every three years, art. 36 transmission |
| EDPB, endorsed WP29 guidelines | <https://www.edpb.europa.eu/our-work-tools/general-guidance/endorsed-wp29-guidelines_en> | WP248 rev.01 is endorsed (item 6) |
| EDPB Endorsement 1/2018 | <https://www.edpb.europa.eu/sites/default/files/files/news/endorsement_of_wp29_documents_en_0.pdf> | same, the endorsement text |
| WP248 rev.01 (the document the EDPB page links to) | <https://ec.europa.eu/newsroom/article29/redirection/document/47711> | the nine criteria, "two criteria", the high-residual-risk example |
| CNIL, *PIA, la méthode* (2018) | <https://www.cnil.fr/sites/cnil/files/atoms/files/cnil-pia-1-fr-methode.pdf> | the four steps, the three feared events, the validation step |
| CNIL, *PIA, les bases de connaissances* (2018) | <https://www.cnil.fr/sites/cnil/files/atoms/files/cnil-pia-3-fr-basesdeconnaissances.pdf> | the severity and likelihood scales, the action-plan scales |
| CNIL, *PIA, les modèles* (2018) | <https://www.cnil.fr/sites/cnil/files/atoms/files/cnil-pia-2-fr-modeles.pdf> | the risk map and action-plan templates |

GDPR articles 35 and 36 are cited by number as WP248 and the CNIL guides quote them; the
EUR-Lex page (<https://eur-lex.europa.eu/eli/reg/2016/679/oj>) refused automated reads on
that date. The cnil.fr HTML pages were in maintenance on that date; the PDFs above were not.
On 2026-11-19 the CNIL-hosted GDPR text (<https://www.cnil.fr/fr/reglement-europeen-protection-donnees>) returned HTTP 503 and the CNIL list of processing exempt from a DPIA (deliberation 2019-118) could not be read; both stay unverified. The script does not apply that exemption list.

Every page above, with its verbatim quote, retrieval date and read/unread status: [`sources.json`](sources.json).

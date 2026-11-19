# DPA review — full reference

## Sources

Every item below rests on one of these, read on the date given. The machine-readable list, with an exact quote per page, is [sources.json](sources.json).

| Source | URL | Read |
|---|---|---|
| GDPR (Regulation (EU) 2016/679), art. 28, 32 to 36 | <https://eur-lex.europa.eu/eli/reg/2016/679/oj> | **not read**: on 2026-11-19 EUR-Lex answered automated fetches with an empty challenge page (HTTP 202), and the CNIL-hosted copy (<https://www.cnil.fr/fr/reglement-europeen-protection-donnees/chapitre4>) answered HTTP 503 (maintenance page). The article wording used here comes from the EDPB guidelines below, which quote and number it item by item |
| EDPB Guidelines 07/2020 on the concepts of controller and processor in the GDPR, version 2.0, adopted 7 July 2021 | <https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-072020-concepts-controller-and-processor-gdpr_en> (PDF: <https://www.edpb.europa.eu/system/files/documents/2023-10/EDPB_guidelines_202007_controllerprocessor_final_en.pdf>) | 2026-11-19: Part II §1.3 (content of the contract, points 114 to 136, 1.3.1 to 1.3.8), §1.5 (art. 28(10)), §1.6 (sub-processors) |
| CNIL, *Guide du sous-traitant*, édition septembre 2017, with its *Exemple de clauses contractuelles de sous-traitance* | <https://www.cnil.fr/sites/default/files/atoms/files/rgpd-guide_sous-traitant-cnil.pdf> | 2026-11-19 (the HTML page <https://www.cnil.fr/fr/guide-sous-traitant> answered HTTP 503) |
| Commission Implementing Decision (EU) 2021/914 (standard contractual clauses for transfers to third countries) | <https://eur-lex.europa.eu/eli/dec_impl/2021/914/oj> | **not read** (same EUR-Lex challenge; no non-EUR-Lex official copy was found). Named only as a mechanism to look for; the skill never assesses the clauses themselves |
| Commission Implementing Decision (EU) 2023/1795 (adequacy decision for the EU-US Data Privacy Framework) | <https://eur-lex.europa.eu/eli/dec_impl/2023/1795/oj> | **not read** (EUR-Lex answered HTTP 202 with an empty body on 2026-11-19). Its effect is taken from the Commission page below, which links to it |
| European Commission, *EU-US data transfers* | <https://commission.europa.eu/law/law-topic/data-protection/international-dimension-data-protection/eu-us-data-transfers_en> | 2026-11-19: data flows under the adequacy decision to US companies that participate in the Data Privacy Framework; standard contractual clauses and binding corporate rules stay usable |
| Data Privacy Framework List and Program Overview (US Department of Commerce) | <https://www.dataprivacyframework.gov/list>, <https://www.dataprivacyframework.gov/Program-Overview> | **not read**: on 2026-11-19 both answered with a JavaScript application shell and no text, to `curl` and to a web-fetch tool. The skill only points the user to the list; it never says whether a company is on it |

Points the review relies on, from the EDPB guidelines:

- The contract must set out the subject-matter, duration, nature and purpose of the
  processing, the type of personal data, the categories of data subjects, and the
  obligations and rights of the controller (point 114). "Personal data pursuant to Article
  4(1)" or "special categories pursuant to Article 9" is not an adequate data type; for
  special categories the contract names which ones (point 114).
- The contract "should not merely restate the provisions of the GDPR" (points 112, 126,
  133): a clause that only paraphrases art. 28 is **WEAK**, not PRESENT.
- The processor notifies the controller of a breach without undue delay; a timeframe in
  hours, a contact point and the minimum content may be set in the contract (point 136).
- Transfers to the United States, from the Commission page: personal data "can flow freely
  from the EU to companies in the United States that participate in the Data Privacy
  Framework", and the safeguards also facilitate "other tools, such as standard contractual
  clauses and binding corporate rules". Whether a recipient participates is read on the
  official DPF list, never inferred from the contract.
- A processor that processes the data for its own purposes is a controller for that
  processing and infringes the GDPR (art. 28(10), §1.5): service improvement or model
  training on customer data is a **RISK** row, always.

## Items

Mandatory items take `PRESENT`, `WEAK` or `MISSING`. Risk items take `RISK` (the contract
says something that exposes the controller), `OK` (the point is addressed in a way that
limits the risk) or `SILENT` (the contract says nothing).

| Id | What PRESENT needs | Typical WEAK |
|---|---|---|
| `28(3)-subject` | the object of the processing, specific enough to know what is processed | "the services" with no description |
| `28(3)-duration` | a period, or the criteria fixing it (e.g. the main agreement's term) | none stated, only "as long as necessary" |
| `28(3)-nature` | the operations performed (hosting, storage, analysis, transcription…) | "processing" with no operations |
| `28(3)-purpose` | the purpose of the processing | purpose left to the processor |
| `28(3)-data` | the types of personal data, named | "personal data" or "art. 9 data" without naming them |
| `28(3)-subjects` | the categories of data subjects | "users" when several populations exist |
| `28(3)-controller` | the controller's obligations and rights | absent: only the processor's side is written |
| `28(3)(a)` | processing only on documented instructions, transfers included | instructions "as the processor sees fit" |
| `28(3)(b)` | persons authorised to process committed to confidentiality | confidentiality of the contract only, not of the data |
| `28(3)(c)` | the art. 32 measures, described or annexed | a bare "appropriate measures" |
| `28(3)(d)` | the sub-processing conditions of 28(2) and 28(4) are referenced | sub-processors mentioned without conditions |
| `28(2)` | prior specific or general written authorisation; with general authorisation, notice of changes and a right to object | notice with no right to object |
| `28(4)` | the same data protection obligations flow down; the processor stays fully liable | flow-down "substantially similar" with no liability |
| `28(3)(e)` | assistance with data subject requests | a paid option with no commitment |
| `28(3)(f)` | assistance with arts. 32 to 36: security, breach notification, DPIA, prior consultation | breach only; DPIA absent |
| `28(3)(g)` | at the controller's choice, deletion or return at the end, and deletion of copies | deletion with no deadline, or return only |
| `28(3)(h)` | information to demonstrate compliance, and audits including inspections by the controller or its mandated auditor | a certificate offered in place of any audit |
| `28(3)-unlawful-instruction` | the processor informs the controller when an instruction infringes data protection law | absent |
| `transfers` | transfers outside the EU/EEA named, with their mechanism (adequacy, standard contractual clauses, binding corporate rules). A transfer to the United States (a US provider or sub-processor, or data processed there) always gets a check in the last column: is the recipient listed as active on the Data Privacy Framework List (<https://www.dataprivacyframework.gov/list>); if not, which other art. 46 mechanism (e.g. standard contractual clauses) does the contract name. A check, never a conclusion | transfers allowed "anywhere the processor operates" |
| `training` | customer data is not used for the processor's own purposes (model training, service improvement, analytics) | — any such use is `RISK` |
| `retention` | retention by the processor bounded, backups included | backups kept indefinitely |
| `breach-delay` | a breach notification delay to the controller, ideally in hours, with a contact point | "without undue delay" only, or a delay above 72 hours |
| `liability` | liability, caps and insurance stated | a cap that excludes data protection claims, no insurance |
| `special-data` | special-category data (health, biometric, genetic…) named when processed. In France, health data hosting may require HDS certification: always a **question for a lawyer**, never a conclusion | special categories processed but not named |

## Vocabulary

The locator reads this block. One item per line: `id :: kind :: English label :: French
label :: pattern`. The pattern is a POSIX extended regex matched against each lowercased
line of the contract; accented letters are written `(e|é)` because lowercasing leaves them
alone. A match is a candidate, never a verdict: the agent reads it and decides.

<!-- dpa-vocab -->
```text
28(3)-subject :: mandatory :: Subject-matter :: Objet du traitement :: subject[- ]matter|object of (the )?processing|objet (du|de la|des) (contrat|traitement|pr(e|é)sent|prestation|sous-traitance)|scope of (the )?processing|pour objet|(—|-|:) *objet *$
28(3)-duration :: mandatory :: Duration :: Durée :: duration|dur(e|é)e|term of (this|the)|entre en vigueur|effective (date|from)|remain in (force|effect)
28(3)-nature :: mandatory :: Nature of the processing :: Nature du traitement :: nature (of|du|de la|des)|processing operations|operations performed|op(e|é)rations? de traitement|hosting|h(e|é)bergement|storage|stockage
28(3)-purpose :: mandatory :: Purpose :: Finalité :: purpose|finalit(e|é)
28(3)-data :: mandatory :: Types of personal data :: Types de données :: (types?|categor(y|ies)) of personal data|(types?|cat(e|é)gories?) de donn(e|é)es|personal data (processed|concerned)|personal data *:|donn(e|é)es (trait(e|é)es|concern(e|é)es|personnelles trait)
28(3)-subjects :: mandatory :: Categories of data subjects :: Catégories de personnes concernées :: data subjects|personnes concern(e|é)es
28(3)-controller :: mandatory :: Controller obligations and rights :: Obligations et droits du responsable :: (obligations|rights) of the (controller|customer)|obligations (et droits )?du responsable|droits du responsable|(controller|customer) shall|responsable (de|du) traitement (s'engage|doit|garantit)|le client s'engage
28(3)(a) :: mandatory :: Documented instructions :: Instructions documentées :: documented instructions?|instructions? document(e|é)es?|on (the )?(controller's |customer's )?instructions?|sur (les )?instructions?|only (for|in accordance with) the purposes?|uniquement (pour|sur)
28(3)(b) :: mandatory :: Confidentiality of authorised persons :: Confidentialité des personnes autorisées :: confidential|confidentialit(e|é)|secret professionnel|obligation of secrecy
28(3)(c) :: mandatory :: Security (art. 32) :: Sécurité (art. 32) :: article 32|art\. ?32|security measures|mesures de s(e|é)curit(e|é)|technical and organi[sz]ational|techniques et organisationnelles|encrypt|chiffr
28(3)(d) :: mandatory :: Engaging sub-processors :: Recours à un sous-traitant ultérieur :: sub-?processors?|sous-traitants? ult(e|é)rieurs?|subcontract|another processor|autre sous-traitant|sous-traitance ult(e|é)rieure
28(2) :: mandatory :: Prior authorisation of sub-processors :: Autorisation préalable des sous-traitants :: (general|specific) (written )?authori[sz]ation|autorisation ((e|é)crite )?(g(e|é)n(e|é)rale|sp(e|é)cifique)|prior (specific |general )?(or general )?(specific )?(written )?authori[sz]ation|autorisation (sp(e|é)cifique |g(e|é)n(e|é)rale )?((e|é)crite )?pr(e|é)alable|right to object|object to (the|such|any|a new)|s'opposer|objections?
28(4) :: mandatory :: Flow-down to sub-processors :: Mêmes obligations pour le sous-traitant ultérieur :: same (data protection )?obligations|m(e|ê)mes obligations|flow[- ]?down|fully liable|pleinement responsable|reste (enti(e|è)rement )?responsable|remains? (fully )?(liable|responsible)
28(3)(e) :: mandatory :: Data subject rights :: Droits des personnes :: data subjects?'? rights|rights of (the )?data subjects|droits des personnes|exercice (de leurs|des) droits|data subject requests?|requests? from data subjects|exercise (of )?(their |his or her )?rights|droit d'acc(e|è)s|rectification|portabilit
28(3)(f) :: mandatory :: Assistance with arts. 32 to 36 :: Aide pour les articles 32 à 36 :: articles? 32 (to|à|-) ?36|impact assessment|analyse d'impact|aipd|dpia|prior consultation|consultation pr(e|é)alable|personal data breach|violations? de donn(e|é)es|notif
28(3)(g) :: mandatory :: Deletion or return at the end :: Suppression ou restitution en fin de contrat :: delet|suppr|efface|return (all |the )*(personal )?data|restitu|renvoyer|destroy|d(e|é)trui|end of (the )?(provision|services|agreement|contract)|fin (du contrat|de la prestation|des services|du pr(e|é)sent)|termination
28(3)(h) :: mandatory :: Audits and inspections :: Audits et inspections :: audit|inspection|demonstrate compliance|d(e|é)montrer le respect|documentation n(e|é)cessaire|information necessary to demonstrate
28(3)-unlawful-instruction :: mandatory :: Infringing instruction flagged :: Instruction contraire signalée :: infring|enfrein|constituer? une violation|contrary to (the )?(gdpr|law|data protection)|contraire (au|à la|aux)|immediately inform|informe imm(e|é)diatement
transfers :: risk :: Transfers outside the EU :: Transferts hors UE :: transfer|transfert|third countr|pays tiers|outside (of )?(the )?(eu|eea|european)|hors (de l'|de l)?(ue|union|eee|espace)|standard contractual clauses|clauses contractuelles types|adequacy|ad(e|é)quation|binding corporate|data privacy framework|united states|tats-unis|u\.s\.|(^|[^a-z])usa([^a-z]|$)
training :: risk :: Use for training or service improvement :: Usage pour entraînement ou amélioration :: train|entra(i|î)n|improv|am(e|é)lior|own purposes|propres fins|propre compte|machine learning|apprentissage|models?|mod(e|è)les?|anonymi|aggregat|agr(e|é)g|de-identif|analytics|statisti
retention :: risk :: Retention by the processor :: Conservation par le sous-traitant :: retain|retention|retenti|conserv|archiv|backups?|sauvegardes?|logs? (are|is) (kept|stored)|journaux
breach-delay :: risk :: Breach notification delay :: Délai de notification des violations :: breach|violation|incident|hours|heures|without undue delay|meilleurs d(e|é)lais|72
liability :: risk :: Liability and insurance :: Responsabilité et assurance :: liabil|responsabilit(e|é)|indemn|insurance|assurance|liability cap| capped|plafon|limitation of
special-data :: risk :: Special-category or health data :: Données sensibles ou de santé :: health|sant(e|é)|medical|m(e|é)dical|patient|special categor|cat(e|é)gories particuli|article 9|art\. ?9|biometric|biom(e|é)tri|genetic|g(e|é)n(e|é)tique|hds|h(e|é)bergeur de donn|h(e|é)bergement de donn
```

## Verdict file

One line per item, every id of the vocabulary exactly once, in any order:

```
<id> :: <STATUS> :: <evidence> :: <what to fix or ask>
```

- `evidence`: the clause heading or number and a short quote, with its `L<n>` from
  `extract`. Required for `PRESENT`, `WEAK`, `RISK` and `OK`. For `MISSING` and `SILENT`,
  `-` or what was searched.
- `what to fix or ask`: required for `WEAK`, `MISSING` and `RISK`; `-` otherwise. Phrase it
  as a fix when the user drafted the contract, as a request to the provider when the user
  must accept it. It may not contain the words "compliant" or "conforme": render refuses
  them, because the review never certifies.

Questions for the lawyer, one per line, at least one:

```
Q :: <question>
```

Blank lines and lines starting with `#` are ignored. Do not use ` :: ` inside a field.

## Rendered output

```
DPA review · <file> · <date> · 18 mandatory: <n> present, <n> weak, <n> missing · <n> risk points

| Item | Status | Evidence | What to fix or ask |
|---|---|---|---|
| 28(3)(a) Documented instructions | PRESENT | §4.1 L25 "…" | - |
…

## Placeholders (<n>)
- L12: [CLIENT NAME]

## Questions for a lawyer
1. …

Not a legal opinion: this lists what the contract contains, lacks or leaves weak against GDPR art. 28. A lawyer decides.
```

`--lang fr` translates the labels, headings and closing line; ids and status tokens stay as
they are.

## Placeholders

`placeholders` reports every `[...]` in the extracted text except markdown links
(`[text](url)`) and numeric references (`[1]`). Placeholders left in a contract the user is
about to send are always reported, even when the agent thinks they are intentional.

## Formats

| Format | Route | Limit |
|---|---|---|
| `.md`, `.txt` | read as is, CR stripped | — |
| `.docx` | `unzip -p` of `word/document.xml`, one paragraph per line, tags stripped | tracked changes and comments are flattened into the text; headers, footers and footnotes are not read |
| `.pdf` | `pdftotext -layout` (poppler) when installed | without it, the script stops and says so: export the PDF to text. A scanned PDF has no text layer and stops with `no text extracted` |
| `.doc`, `.odt`, others | none | export to `.docx`, `.md` or `.txt` first |

## Failure lines

The script exits non-zero and names the cause on its last stderr line.

| Exit | Cause |
|---|---|
| 2 | bad usage: unknown subcommand or flag, missing argument |
| 3 | the contract cannot be read: missing file, unsupported format, no `unzip` or `pdftotext`, no text extracted |
| 1 | `render` refused the verdict file: each problem on its own line (unknown or duplicate id, item missing, status outside the vocabulary, empty evidence or fix, no question, "compliant"/"conforme" in a fix) |

`render` never prints a partial table: a verdict that fails validation prints nothing on
stdout.

## Limits

The locator is a regex over lines: it misses a clause written in words it does not list,
and it matches words used in another sense. That is why every item is decided by the agent
reading the contract, and why an item with no candidate is marked `MISSING` only after the
whole text has been read. The review covers art. 28 and the listed risk points; it does not
assess the standard contractual clauses themselves, a transfer impact assessment, national
law beyond the HDS question, or the main services agreement.

# Melito of Sardis, *Peri Pascha*

Structured research corpus and static reading site for Melito of Sardis' *Peri Pascha*.

## Contents

- Compact line-by-line analysis in `analysis_*.jsonl`
- Full merged corpus in `analysis_all.jsonl`
- Reconstructed reading text in `clean_greek_full.txt`
- Token and lemma exports in `tokens.csv` and `lemma_index.csv`
- QA report in `analysis_qa_report.json`
- Static reading site in `site/`

## Local regeneration

The site payload in `site/data.js` is generated from the canonical corpus files:

```bash
PYTHONPATH=src python3 -m melito.analysis_exports --root .
```

## Local preview

```bash
python3 -m http.server 8123 --directory site
```

Then open `http://127.0.0.1:8123/`.


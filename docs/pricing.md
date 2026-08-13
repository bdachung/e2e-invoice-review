# Pricing

Pricing checked on 2026-07-19 for the project's Document Intelligence resource and the `gpt-5.6-terra` Global Standard deployment. Azure prices are estimates: the final amount can vary by agreement, purchase date, tax, and exchange rate. Microsoft publishes current service prices through the [Azure Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices).

## Cost of this local setup

| Component | Tier | Standing cost | Usage cost in this project |
| --- | --- | ---: | ---: |
| Azure resource group | Platform container | €0 | €0 |
| Azure Document Intelligence | F0 in West Europe | €0 | First 500 analyzed pages per month are free |
| Azure OpenAI `gpt-5.6-terra` | Global Standard in Sweden Central | $0 | Two token-metered calls per upload; an optional third call only when a correction email is requested |
| FastAPI, React, SQLite, uploaded files | Developer machine | No Azure charge | Local resources only |
| Hosting, managed database, object storage | Not deployed | €0 | €0 |

The public short-context meters used here are $2.50 per million input tokens and $15.00 per million output tokens. The recognition/review call sends the source PDF, PNG, or JPEG to Azure OpenAI. It classifies the document and can supplement fields left empty by Document Intelligence. The GL suggestion sends only normalized fields and the fixed account catalog. A correction-email request sends normalized fields plus supplier-fixable issues, not the source file.

F0 processes up to 500 pages per month. Each request is limited to the first two pages, 4 MB, and one analyze transaction per second. Azure bills Document Intelligence by pages analyzed, not by files or requests. See Microsoft's [billing and service-limit documentation](https://learn.microsoft.com/azure/ai-services/document-intelligence/service-limits?view=doc-intel-4.0.0#billing).


## Cost of the schema mapping experiment

The playground mapping experiment sends one one-page fictional invoice to
`prebuilt-invoice` and one one-page fictional fuel receipt to `prebuilt-receipt`:
two requests and two pages. On the current F0 resource this is within the 500-page
monthly allowance (0.4%); at the S0 USD reference rate it is about $0.02. The
experiment only writes ignored local JSON files under `playground/`; remove those
files to clean up the local output.

The document-classification pipeline adds one Azure OpenAI call per uploaded document before Document Intelligence is selected. Its prompt contains the source PDF or image and should be treated as a separately metered call when estimating an end-to-end workflow.

## Cost of one extraction evaluation

The evaluator sends 12 invoices to `prebuilt-invoice` and one fuel receipt to `prebuilt-receipt`: 13 requests and 14 pages.

| Scenario | Price | Calculation | Full evaluation |
| --- | ---: | ---: | ---: |
| Current F0 resource | 500 pages/month free | 14 pages within allowance | **€0.00** |
| S0, USD retail | $10.00 / 1,000 prebuilt pages | 14 × $10 / 1,000 | **$0.14** |
| S0, EUR reference | €8.7758 / 1,000 prebuilt pages | 14 × €8.7758 / 1,000 | **€0.1229**, about **€0.12** |

One run uses 2.8% of the F0 allowance. In an otherwise unused month it fits 35 complete runs (490 pages), with ten pages left. Single-document checks and UI uploads consume the same allowance. F0 has no paid overage: after its quota is exhausted, use S0 or wait for the monthly reset.

## Cost of the complete hybrid evaluation

The extraction evaluator does not call Azure OpenAI. Running all 13 documents through the complete application makes two model calls per document:

1. Recognition and independent extraction: at most 8,000 input and 500 output tokens per document.
2. GL suggestion: at most 2,000 input and 100 output tokens per document.

For PDFs, the Responses API includes extracted text and page images in model context, so exact token usage varies with the document. Microsoft describes this in [PDF input for the Responses API](https://learn.microsoft.com/en-gb/azure/foundry/openai/how-to/responses?tabs=python-key#pdf-files). These are transparent planning envelopes, not fixed transaction prices.

```text
recognition/review input:  13 × 8,000 = 104,000 × $2.50 / 1M = $0.2600
recognition/review output: 13 ×   500 =   6,500 × $15.00 / 1M = $0.0975
recognition/review total                                      = $0.3575

GL input:                 13 × 2,000 = 26,000 × $2.50 / 1M = $0.0650
GL output:                13 ×   100 =  1,300 × $15.00 / 1M = $0.0195
GL total                                                       = $0.0845

complete 13-document Azure OpenAI envelope                     = $0.4420
```

The complete set is therefore about **$0.44**, plus **€0.00** for Document Intelligence while the F0 allowance remains. One ordinary hybrid document is about **$0.034** under the same two-call envelope. Dense or multi-page documents can cost more; short receipts can cost less. Responses are not cached, so deleting and reprocessing creates new usage.

## Optional correction-email cost

The correction-email model is not called during upload. It runs only when a reviewer clicks **Generate correction email**, and only for a deterministic issue the supplier can fix.

```text
input:  2,000 × $2.50 / 1M = $0.0050
output:   500 × $15.00 / 1M = $0.0075
one optional draft          = $0.0125, about 1.25 cents
```

The call returns copyable text only. It does not send an email or incur an email-provider charge.

## Recheck the calculation

Count the committed corpus:

```bash
jq '{documents: length, pages: ([.[].pages] | add)}' samples/manifest.json
```

Expected:

```json
{
  "documents": 13,
  "pages": 14
}
```

Query the live S0 prebuilt meter for West Europe:

```bash
for currency in USD EUR; do
  curl -sG 'https://prices.azure.com/api/retail/prices' \
    --data-urlencode "currencyCode=$currency" \
    --data-urlencode "\$filter=armRegionName eq 'westeurope' and productName eq 'Azure Document Intelligence' and skuName eq 'S0' and meterName eq 'S0 Pre-built Pages'" \
    | jq '.Items[] | {currencyCode, retailPrice, unitOfMeasure, meterName}'
done
```

Query the current Global Standard short-context token meters:

```bash
curl -sG 'https://prices.azure.com/api/retail/prices' \
  --data-urlencode 'api-version=2023-01-01-preview' \
  --data-urlencode "\$filter=productName eq 'Azure OpenAI GPT5' and contains(skuName, '5.6 terra')" \
  | jq '[.Items[] | select(.armRegionName == "swedencentral") | select(.skuName == "5.6 terra ShortCo Inp Std Gl" or .skuName == "5.6 terra ShortCo Opt Std Gl") | {skuName, retailPrice, currencyCode, unitOfMeasure}] | unique_by(.skuName)'
```

Use Azure Cost Management for the subscription's actual billed amount. The Retail Prices API does not include negotiated discounts or taxes.

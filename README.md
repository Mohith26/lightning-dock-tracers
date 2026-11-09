# lightning-dock-tracers

Tracer-test and production-temperature analysis of the Lightning Dock geothermal field (Hidalgo County, New Mexico), built on the data package Zanskar published to the Geothermal Data Repository in August 2026: [GDR submission 1856](https://gdr.openei.org/submissions/1856) (CC BY 4.0).

I wanted to see whether the public data alone could tie the field's 2020-2024 cooling to injector-producer connectivity. This repo pulls only the four CSVs it needs out of the 7.4 GB package (HTTP range requests on the zip files, about 3 MB downloaded), computes moment-based tracer metrics, fits temperature trends, and runs a few consistency checks on the tables.

```
pip install -e ".[test]"
python -m ldtracer.report      # fetches the CSVs into ./data, writes ./results
pytest                         # 14 tests; the real-data tests run once ./data exists
```

## What it computes

- **Tracer returns** (`ldtracer.tracer`): for each injector/producer pair, first detection, peak, recovered mass (trapezoidal integral of concentration times producer flow, with flow interpolated from `well_flow_rates.csv`), recovery fraction, mean residence time (first moment of the mass rate), and swept volume after Shook (2005) when the injected mass is known. Censored samples count as zero.
- **Temperature trends** (`ldtracer.thermal`): least-squares slope on monthly medians of the daily reports, after dropping values outside 150-400 F.
- **Checks** (`ldtracer.qa`): lab-report rows against consolidated rows for the same sample, and out-of-range temperatures.

## Results

2016 campaign, 50 kg of each naphthalene sulfonate, ~130 days of sampling (`results/tracer_2016.csv`):

| injector | producer | first detect (d) | peak (d) | recovered | mean residence (d) |
|---|---|---|---|---|---|
| 66A-7 | 55-7 | 4.0 | 8.0 | 53.4% | 39 |
| 75-7 | 55-7 | 5.4 | 37.4 | 20.8% | 54 |
| 53-7 | 45-7 | 18.9 | 37.4 | 26.8% | 74 |
| 53-7 | 55-7 | 5.4 | 104.9 | 11.2% | 56 |
| 66A-7 | 45-7 | 29.0 | 128.0 | 1.5% | 92 |
| 75-7 | 45-7 | 32.0 | 122.2 | 1.3% | 95 |

2019 campaign (`results/tracer_2019.csv`). The package has no injected masses for 2019, so only timing is reported: tracer from 55-7 reached the new producer 45A-7 in about 1 day (peak 360 ug/L at day 5), and tracer from 53-7 reached 45A-7 in 2 days and 45-7 in 3 days. 17-7 and 75-7 tracers were not detected at either producer in ~238 days.

Production temperature (`results/temperature_trends.csv`, `results/production_temperature.png`):

| series | window | trend |
|---|---|---|
| plant supply | 2016-2019 | -0.7 F/yr (+/- 0.1) |
| plant supply | 2020-2024 | -9.8 F/yr (+/- 0.3) |
| well 45-7 | 2020-2024 | -11.8 F/yr (+/- 0.3) |
| well 45A-7 | 2020-2024 | -8.8 F/yr (+/- 0.3) |

Supply temperature fell from a 312 F median in 2016 to 258 F in 2024 and returned to 320-321 F after well 44-7 came online in 2025 (321 F median).

Reading these together: the injectors with the fastest, largest returns in 2016 and 2019 (66A-7, 53-7, 55-7) are the ones a few days of travel time from the producers, and the steep decline begins when 45A-7 started producing in 2020. That is consistent with cooler injectate breaking through, but this analysis does not prove the mechanism; flow allocation between wells also changed over the period.

## Data checks worth knowing about

- In 2016 the tracer table holds two copies of many samples: a consolidated series (with `days_since_injection`) and rows transcribed from the lab reports (with `lab_sample_no`, no elapsed time). 375 pairs line up; 49 differ by more than 50%, and every one of them is compound `2 NS`. On those dates the lab reports list two different `2 NS` values for the same sample (for example 0.15 and 6.78 ug/L at 45-7 on 2016-08-10, against 1.05 consolidated), which suggests two analytes mapped to one name. Swapping in either lab value moves the 53-7 recoveries only slightly (45-7: 26.7-27.2%, 55-7: 9.8%), so the table above uses the consolidated series.
- `tracer_injections.csv` has no `amount_kg` for 2019 or 2017, so recovery fractions cannot be computed for those campaigns from the package alone.
- The daily reports contain a few impossible temperatures (for example 0.005 F and 4,710 F): 80 of 3,760 supply values and 11 producer values fall outside 150-400 F (`results/qa_temperature_out_of_range.csv`). The trend fits drop them and use monthly medians.

## What was not done

No reservoir model, no thermal-breakthrough prediction, and no use of the 2012 dye test, the 2017 cesium test, the well logs or the geophysics. Results depend on the published CSVs; I did not re-derive anything from the original lab PDFs.

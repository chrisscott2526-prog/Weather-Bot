# Model report -- who forecasts each city best

Median miss (degrees F) between each model's night-before
forecast and the officially settled number, per city; the
signed lean in brackets (+ runs hot, - runs cold). `pool` is
the calibrated GFS+ECMWF median the money actually used;
`gfs`/`ecmwf` are its two voters graded separately (also
calibrated); `icon`/`nws` are raw research passengers riding
along -- a passenger that ties the calibrated incumbents is
doing well. Small n means luck still speaks louder than
skill. RESEARCH ONLY: no trading or calibration code reads
this file, and promotion of any model into the vote is an
owner decision. Regenerated in full by model_report.py.

| city | pool | ecmwf | gfs | icon | nws |
|---|---|---|---|---|---|
| Atlanta | 1.1 (-0.6) n=16 | 1.9 (+1.9) n=1 | 3.3 (+3.3) n=1 | 0.5 (+0.5) n=1 | 1.5 (+1.5) n=1 |
| Austin | 1.4 (-0.8) n=14 | 1.1 (-1.1) n=1 | 3.1 (-3.1) n=1 | 2.1 (-2.1) n=1 | 1.5 (-1.5) n=1 |
| Boston | 2.5 (-2.5) n=9 | 2.5 (+2.5) n=1 | 0.6 (-0.6) n=1 | 1.3 (-1.3) n=1 | 0.5 (-0.5) n=1 |
| Chicago | 1.6 (-1.2) n=13 | 2.2 (-2.2) n=1 | 2.1 (-2.1) n=1 | 0.0 (+0.0) n=1 | 2.5 (-2.5) n=1 |
| Dallas | 1.4 (-0.5) n=13 | 2.8 (-2.8) n=1 | 2.0 (-2.0) n=1 | 0.2 (-0.2) n=1 | 0.5 (-0.5) n=1 |
| Denver | 2.1 (-1.8) n=13 | 4.1 (-4.1) n=1 | 0.9 (-0.9) n=1 | 5.1 (-5.1) n=1 | 2.5 (-2.5) n=1 |
| Houston | 1.0 (+0.4) n=12 | - | - | - | - |
| Las Vegas | 2.6 (-1.9) n=14 | 0.9 (+0.9) n=1 | 0.1 (+0.1) n=1 | 3.0 (-3.0) n=1 | 0.5 (+0.5) n=1 |
| Los Angeles | 3.2 (+3.2) n=11 | 2.9 (+2.9) n=1 | 3.9 (-3.9) n=1 | 0.4 (-0.4) n=1 | 1.5 (-1.5) n=1 |
| Miami | 1.8 (-1.8) n=16 | 1.4 (-1.4) n=1 | 2.1 (+2.1) n=1 | 1.2 (+1.2) n=1 | 1.5 (+1.5) n=1 |
| Minneapolis | 1.6 (-0.6) n=10 | 2.5 (-2.5) n=1 | 2.7 (+2.7) n=1 | 3.5 (-3.5) n=1 | 0.5 (+0.5) n=1 |
| New Orleans | 1.8 (-1.6) n=13 | 2.9 (-2.9) n=1 | 2.4 (+2.4) n=1 | 3.7 (-3.7) n=1 | 1.5 (+1.5) n=1 |
| New York City | 2.2 (-0.2) n=10 | - | - | - | - |
| Oklahoma City | 2.1 (-1.5) n=11 | 1.5 (-1.5) n=1 | 1.6 (+1.6) n=1 | 1.6 (-1.6) n=1 | 1.5 (-1.5) n=1 |
| Philadelphia | 1.1 (-0.4) n=14 | 3.1 (-3.1) n=1 | 1.7 (-1.7) n=1 | 5.4 (-5.4) n=1 | 2.5 (-2.5) n=1 |
| Phoenix | 1.3 (-1.1) n=12 | 5.6 (-5.6) n=1 | 0.7 (+0.7) n=1 | 2.8 (-2.8) n=1 | 1.5 (+1.5) n=1 |
| San Antonio | 1.0 (-0.5) n=14 | 1.2 (+1.2) n=1 | 0.8 (-0.8) n=1 | 1.3 (+1.3) n=1 | 0.5 (+0.5) n=1 |
| San Francisco | 4.0 (+2.7) n=12 | 6.9 (-6.9) n=1 | 4.4 (-4.4) n=1 | 4.6 (-4.6) n=1 | 3.5 (-3.5) n=1 |
| Seattle | 2.9 (-1.8) n=12 | - | - | - | - |
| Washington DC | 1.5 (-1.3) n=13 | 2.5 (-2.5) n=1 | 0.2 (+0.2) n=1 | 5.1 (-5.1) n=1 | 2.5 (-2.5) n=1 |

## Overall (all cities pooled)

- **nws**: median miss 1.50F, lean -0.50F, n=17
- **pool**: median miss 1.60F, lean -0.70F, n=252
- **gfs**: median miss 2.00F, lean -0.60F, n=17
- **icon**: median miss 2.10F, lean -2.10F, n=17
- **ecmwf**: median miss 2.50F, lean -2.20F, n=17

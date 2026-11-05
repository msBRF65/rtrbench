# Loop timing results

Times are main-thread wall time inside existing compute ROIs; paused rollouts, input loading and builds are excluded.
Parts are exclusive: inner regions replace parent time; unattributed ROI is retained. Means and population standard deviations are in milliseconds.
Negative baseline-to-instrumented changes reflect run noise and code-layout effects, not negative timer cost or a speedup.

| Benchmark | n | ROI-only baseline mean ± std (ms) | Instrumented mean ± std (ms) | Observed change |
|---|---:|---:|---:|---:|
| 01.pfl | 5 | 15.0967 ± 0.592 | 15.4892 ± 0.0784 | +2.6% |
| 02.ekfslam | 5 | 0.611683 ± 0.0218 | 0.528595 ± 0.0186 | -13.6% |
| 04.pp2d | 5 | 245.782 ± 6.81 | 248.509 ± 8.76 | +1.1% |
| 05.pp3d | 5 | 0.328453 ± 0.0105 | 0.318909 ± 0.0117 | -2.9% |
| 06.movtar | 5 | 1295.9 ± 30.4 | 1327.42 ± 27.2 | +2.4% |
| 07.prm | 5 | 3.97228 ± 0.0293 | 3.93337 ± 0.224 | -1.0% |
| 08.rrt | 5 | 8.93412 ± 0.274 | 9.02884 ± 0.39 | +1.1% |
| 09.rrtstar | 5 | 27.2236 ± 0.769 | 27.3988 ± 1.18 | +0.6% |
| 10.rrtpp | 5 | 14.8202 ± 0.503 | 14.8268 ± 0.621 | +0.0% |
| 11.sym-blkw | 5 | 0.964593 ± 0.0312 | 0.972687 ± 0.0426 | +0.8% |
| 12.sym-fext | 5 | 242.105 ± 5.96 | 252.437 ± 4.25 | +4.3% |
| 13.dmp | 5 | 0.018548 ± 0.00485 | 0.0177988 ± 0.00399 | -4.0% |
| 14.mpc | 5 | 16.4417 ± 0.632 | 16.6766 ± 0.628 | +1.4% |
| 15.cem | 5 | 0.0437142 ± 0.00499 | 0.0479938 ± 0.00477 | +9.8% |
| 16.bo | 5 | 0.0417042 ± 0.00444 | 0.0473428 ± 0.00433 | +13.5% |

benchmark-times.png shows one ordinary mean compute-ROI bar per benchmark. Each benchmark PNG shows region names on one shared time axis, with Other for all ROI time outside the named regions. Whiskers show population standard deviation; values above bars are milliseconds. Only PNG figures are produced.
regions.csv ranks the measured loop-containing regions. This is curated source instrumentation, not exhaustive automatic detection of every C++ loop. Source file/symbol coverage is in tools/regions.json and the raw samples retain callsites.
Each chart describes these bundled representative inputs, not a general comparison of algorithm performance. Very short regions can be dominated by timing overhead; zero-resolution observations do not prove zero work.

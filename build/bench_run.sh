cd ~/Desktop/重力乐园
B=/Applications/Blender.app/Contents/MacOS/Blender
./scripts/run_pipeline.sh > build/pipeline_v3.log 2>&1
rm -f build/bench_tiers.json
for T in eevee c32 c64 c128 c64fast; do
  $B -b blend/重力乐园.blend -P scripts/bench_tiers.py -- $T 1.0 26.0 42.0 2>&1 | grep -E "BENCH|Error|Traceback|no raytracing" >> build/bench.log
done
echo BENCH_ALL_DONE >> build/bench.log

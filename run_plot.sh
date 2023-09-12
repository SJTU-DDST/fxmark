# rm -rf logs;
# rm -rf cpu*;

bin/plotter.py --ty sc-matplotlib-plotter --log logs/*/fxmark.log --out out;
chown congyong ./out/ -R;
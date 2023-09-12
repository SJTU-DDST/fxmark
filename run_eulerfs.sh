rm -rf logs;
rm -rf cpu*;

bin/run-fxmark.py;
chown congyong ./logs/ -R;

bin/plotter.py --ty sc-matplotlib-gen --log logs/*/fxmark.log --out out;
chown congyong ./out/ -R;
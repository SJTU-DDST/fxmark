rm -rf logs;
rm -rf out;
rm -rf cpu*;
bin/run-fxmark.py;
chown congyong ./logs/ -R;

bin/plotter.py --ty sc-matplotlib --log logs/*/fxmark.log --out out;
chown congyong ./out/ -R;

# bin/plotter.py --ty util --log logs/*/fxmark.log --ncore 1 --out cpu1;
# chown congyong ./cpu1/ -R;
# bin/plotter.py --ty util --log logs/*/fxmark.log --ncore 2 --out cpu2;
# chown congyong ./cpu2/ -R;
# bin/plotter.py --ty util --log logs/*/fxmark.log --ncore 4 --out cpu4;
# chown congyong ./cpu4/ -R;
# bin/plotter.py --ty util --log logs/*/fxmark.log --ncore 8 --out cpu8;
# chown congyong ./cpu8/ -R;
# bin/plotter.py --ty util --log logs/*/fxmark.log --ncore 16 --out cpu16;
# chown congyong ./cpu16/ -R;
# bin/plotter.py --ty util --log logs/*/fxmark.log --ncore 32 --out cpu32;
# chown congyong ./cpu32/ -R;

# legacy
# bin/plotter.py --ty sc --log logs/*/fxmark.log --out out;
# python3 convert.py
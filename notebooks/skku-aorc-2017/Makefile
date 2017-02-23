
localhost:
	PYTHONPATH=../../src/ jupyter-notebook

fatberry.dsi.unifi.it:
	PYTHONPATH=../../src/ jupyter-notebook --port=5900 --ip=150.217.37.50

presentation:
	jupyter-nbconvert talk.ipynb \
        --to slides \
        --reveal-prefix http://cdn.bootcss.com/reveal.js/3.1.0
	cat ../styles/custom-style.js >> talk.slides.html

publish:
	cp talk.slides.html ~/Developer/working-copies/personal-stuff/massimo-nocentini.github.io/PhD/skku-aorc-2017/oeistools.html

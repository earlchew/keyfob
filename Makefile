TEST_PYPI = https://test.pypi.org/legacy/
LIVE_PYPI = https://upload.pypi.org/

TWINE = PYTHONPATH='$(CURDIR)/mfg'"$${PYTHONPATH+:$$PYTHONPATH}" python -m twine

all:
	false

upload:		package
	$(TWINE) upload --repository-url "$(LIVE_PYPI)" dist/keysafe-*.tar.gz

testupload:	package
	$(TWINE) upload --repository-url "$(TEST_PYPI)" dist/keysafe-*.tar.gz

package:
	rm -rf dist
	python setup.py sdist

twine:	mfg/twine

mfg/twine:
	rm -rf mfg
	pip install --target mfg twine

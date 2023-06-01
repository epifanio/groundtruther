# zip current directory excluding git files, __pycache__ directory, qtui directory, help directory, and this script
# Usage: ./make_zip.sh groundtruther

cd ../ ; zip -r $1.zip ./groundtruther -x \*.git\* -x \*__pycache__\* -x \*make_zip.sh\* -x \*qtui\* -x \*help\*


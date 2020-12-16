from app import app
from lxml import etree
from glob import glob
import os
from flask import render_template

namespaces = {'tei': 'http://www.tei-c.org/ns/1.0'}
xmls = glob('xmls/*.xml', )
name_dict = dict()
for x in xmls:
    xml = etree.parse(x)
    for t in xml.xpath('/tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title/text()', namespaces=namespaces):
        name_dict[os.path.basename(x)] = t

@app.route('/')
@app.route('/index')
def index():
    return "Hello, World!"


@app.route('/handschriften')
def handschriften():
    return render_template('handschriften.html', title='Handschriftenliste', handschriften_dict=name_dict)


@app.route('/handschrift/<manuscript>')
def handschrift(manuscript: str):
    return render_template('handschrift.html', title=name_dict[manuscript])

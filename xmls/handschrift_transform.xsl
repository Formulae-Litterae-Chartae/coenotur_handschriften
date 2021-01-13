<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="xs tei"
    version="1.0">
    
    <xsl:output method="html" omit-xml-declaration="yes" indent="yes"/>
    
    <xsl:param name="altIds">
        <xsl:for-each select="/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msIdentifier/tei:altIdentifier">
            <xsl:value-of select="@source"/><xsl:text> </xsl:text><xsl:value-of select="./tei:idno/text()"/>
            <xsl:if test="not(position() = last())"><xsl:text>; </xsl:text></xsl:if>
        </xsl:for-each>
    </xsl:param>
    <xsl:param name="msTitle">
        <xsl:value-of select="/tei:TEI/tei:teiHeader/tei:fileDesc/tei:titleStmt/tei:title/text()"/>
    </xsl:param>
    <xsl:param name="contents">
        <xsl:for-each select="/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msContents/tei:msItem">
            <item>
                <class><xsl:value-of select="@class"/></class>
                <author>
                    <xsl:for-each select="tei:author">
                        <xsl:value-of select="./text()"/>
                        <xsl:if test="not(position() = last())">
                            <xsl:text>, </xsl:text>
                        </xsl:if>
                    </xsl:for-each>
                </author>
                <title>
                    <xsl:for-each select="tei:title">
                        <xsl:value-of select="./text()"/>
                        <xsl:if test="not(position() = last())">
                            <xsl:text>, </xsl:text>
                        </xsl:if>
                    </xsl:for-each>
                </title>
                <language>
                    <xsl:for-each select="tei:textLang">
                        <xsl:variable name="lang" select="@mainLang"/>
                        <xsl:choose>
                            <xsl:when test="$lang = 'la'"><xsl:text>Latein</xsl:text></xsl:when>
                            <xsl:otherwise><xsl:value-of select="$lang"/></xsl:otherwise>
                        </xsl:choose>
                        <xsl:if test="not(position() = last())">
                            <xsl:text>, </xsl:text>
                        </xsl:if>
                    </xsl:for-each>
                </language>
                <locus>
                    <xsl:for-each select="tei:locus">
                        <xsl:choose>
                            <xsl:when test="@from"><xsl:value-of select="@from"/><xsl:if test="@to"><xsl:text>-</xsl:text><xsl:value-of select="@to"/></xsl:if></xsl:when>
                            <xsl:otherwise><xsl:value-of select="@n"/></xsl:otherwise>
                        </xsl:choose>
                        <xsl:if test="not(position() = last())">
                            <xsl:text>/</xsl:text>
                        </xsl:if>
                    </xsl:for-each>
                </locus>
                <parts>
                    <xsl:for-each select="tei:msItem">
                        <item>
                            <title>
                                <xsl:for-each select="tei:title">
                                    <xsl:value-of select="./text()"/>
                                    <xsl:if test="not(position() = last())">, </xsl:if>
                                </xsl:for-each>
                            </title>
                            <locus>
                                <xsl:for-each select="tei:locus">
                                    <xsl:choose>
                                        <xsl:when test="@from"><xsl:value-of select="@from"/><xsl:if test="@to"><xsl:text>-</xsl:text><xsl:value-of select="@to"/></xsl:if></xsl:when>
                                        <xsl:otherwise><xsl:value-of select="@n"/></xsl:otherwise>
                                    </xsl:choose>
                                    <xsl:if test="not(position() = last())">
                                        <xsl:text>/</xsl:text>
                                    </xsl:if>
                                </xsl:for-each>
                            </locus>
                        </item>
                    </xsl:for-each>
                </parts>
            </item>
        </xsl:for-each>
    </xsl:param>
    <xsl:key name="uniqueLangs" match="/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msContents/tei:msItem/tei:textLang/@mainLang" use="." />
    <xsl:key name="uniqueClasses" match="/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msContents/tei:msItem/@class" use="." />
    
    <xsl:template match="/">
        <div class="row">
            <div class="col">
                <h1><xsl:value-of select="$msTitle"/></h1>
                <table class="table table-hover">
                    <tr>
                        <th scope="row">Bezeichnung</th>
                        <td><xsl:value-of select="$msTitle"/></td>
                    </tr>
                    <xsl:if test="count($altIds) > 0">
                    <tr>
                        <th scope="row">Alte Signaturen/Katalognummern</th>
                        <td><xsl:value-of select="$altIds"/></td>
                    </tr>
                    </xsl:if>
                    <xsl:if test="count($contents) > 0">
                        <tr>
                            <th scope="row">Autor bzw. Sachtitel oder Inhaltsbeschreibung</th>
                            <td>
                                <ul class="list-unstyled mb-0">
                                    <xsl:for-each select="$contents/item">
                                        <li><xsl:if test="locus/text()"><xsl:value-of select="locus/text()"/><xsl:text> - </xsl:text></xsl:if>
                                            <xsl:if test="author/text()"><xsl:value-of select="author/text()"/><xsl:text>, </xsl:text></xsl:if>
                                            <xsl:value-of select="title/text()"/>
                                            <xsl:if test="count(parts/item) > 0">
                                                <ul>
                                                <xsl:for-each select="parts/item">
                                                    <li><xsl:value-of select="locus/text()"/><xsl:text> - </xsl:text><xsl:value-of select="title/text()"/></li>
                                                </xsl:for-each>
                                                </ul>
                                            </xsl:if>
                                        </li>
                                    </xsl:for-each>
                                </ul>
                            </td>
                        </tr>
                        <tr>
                            <th scope="row">Sprache</th>
                            <td>
                                <xsl:for-each select="/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msContents/tei:msItem/tei:textLang/@mainLang[generate-id() = generate-id(key('uniqueLangs',.)[1])]">
                                    <xsl:choose><xsl:when test=". = 'la'"><xsl:text>Latein</xsl:text></xsl:when><xsl:otherwise><xsl:value-of select="."/></xsl:otherwise></xsl:choose><xsl:if test="not(position() = last())"><xsl:text>, </xsl:text></xsl:if>
                                </xsl:for-each>
                            </td>
                        </tr>
                        <tr>
                            <th scope="row">Thema / Text- bzw. Buchgattung</th>
                            <td>
                                <xsl:for-each select="/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:msContents/tei:msItem/@class[generate-id() = generate-id(key('uniqueClasses',.)[1])]">
                                    <xsl:value-of select="."/><xsl:if test="not(position() = last())"><xsl:text>, </xsl:text></xsl:if>
                                </xsl:for-each>
                            </td>
                        </tr>
                    </xsl:if>
                    <tr>
                        <th class="text-center" scope="col" colspan="2"><h4>ÄUßERES</h4></th>
                    </tr>
                    
                    <xsl:if test="/tei:TEI/tei:teiHeader/tei:fileDesc/tei:sourceDesc/tei:msDesc/tei:history/tei:origin/tei:p/tei:origPlace">
                        <tr>
                            <th scope="row">Entstehungsort</th>
                            <td>{{ m_d['origin']['place']|join('; ') }}</td>
                        </tr>
                    </xsl:if>
                    {% if m_d['origin']['date'] %}
                    <tr>
                        <th scope="row">Entstehungszeit</th>
                        <td>{{ m_d['origin']['date']|join('; ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['origin']['commentary'] %}
                    <tr>
                        <th scope="row">Kommentar zu Ort und Zeit</th>
                        <td>{{ m_d['origin']['commentary']|join('. ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['obj_form'] %}
                    <tr>
                        <th scope="row">Überlieferungsform</th>
                        <td>{{ m_d['obj_form']|capitalize }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['obj_material'] %}
                    <tr>
                        <th scope="row">Beschreibstoff</th>
                        <td>{{ m_d['obj_material'] }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['num_pages'] %}
                    <tr>
                        <th scope="row">Blattzahl</th>
                        <td>{{ m_d['num_pages'] }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['page_size'] %}
                    <tr>
                        <th scope="row">Format</th>
                        <td>{{ m_d['page_size'] }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['dim_written'] %}
                    <tr>
                        <th scope="row">Schriftraum</th>
                        <td>{{ m_d['dim_written'] }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['num_columns'] %}
                    <tr>
                        <th scope="row">Spalten</th>
                        <td>{{ m_d['num_columns'] }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['written_lines'] %}
                    <tr>
                        <th scope="row">Zeilen</th>
                        <td>{{ m_d['written_lines'] }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['script_desc'] %}
                    <tr>
                        <th scope="row">Schriftbeschreibung</th>
                        <td>{{ m_d['script_desc']|join(', ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['hand_desc'] %}
                    <tr>
                        <th scope="row">Angaben zu Schrift / Schreibern</th>
                        <td>{{ m_d['hand_desc']|join('. ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['layout_notes'] %}
                    <tr>
                        <th scope="row">Layout</th>
                        <td>{{ m_d['layout_notes']|join('. ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['binding'] %}
                    <tr>
                        <th scope="row">Einband</th>
                        <td>{{ m_d['binding']|join('. ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['condition'] %}
                    <tr>
                        <th scope="row">Zustand</th>
                        <td>{{ m_d['condition']|join('. ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['marginal'] %}
                    <tr>
                        <th scope="row">Ergänzungen und Benutzungsspuren</th>
                        <td>
                            {% for n in m_d['marginal'] %}
                            - {{ n }}<br/>
                            {% endfor %}
                        </td>
                    </tr>
                    {% endif %}
                    {% if m_d['exlibris'] %}
                    <tr>
                        <th scope="row">Exlibris</th>
                        <td>{{ m_d['exlibris']|join('; ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['provenance'] %}
                    <tr>
                        <th scope="row">Provenienz</th>
                        <td>{{ m_d['provenance']|join('; ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['provenance_notes'] %}
                    <tr>
                        <th scope="row">Geschichte der Handschrift</th>
                        <td>{{ m_d['provenance_notes']|join('. ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['bibliography'] %}
                    <tr>
                        <th scope="row">Bibliographie</th>
                        <td>{{ m_d['bibliography']|join('; ') }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['online_description'] %}
                    <tr>
                        <th scope="row">Online Beschreibung</th>
                        <td>{{ m_d['online_description']|join('; ')|safe }}</td>
                    </tr>
                    {% endif %}
                    {% if m_d['digital_representations'] %}
                    <tr>
                        <th scope="row">Digitalisat</th>
                        <td>{{ m_d['digital_representations']|join('; ')|safe }}</td>
                    </tr>
                    {% endif %}
                </table>
            </div>
        </div>
    </xsl:template>
    
</xsl:stylesheet>
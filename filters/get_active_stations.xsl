<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet 
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:doc="http://www.pnp-software.com/XSLTdoc"
    exclude-result-prefixes="xs xsi doc" 
    version="2.0">              
        
    <xsl:output   
        indent="yes"
        method="xml"
        encoding="UTF-8" 
    />
    
    <xsl:template match="osm">
        <xsl:document>
            <osm>
                <xsl:copy-of select="ancestor-or-self::osm/@version" />
                <xsl:copy-of select="bounds" />
                <xsl:apply-templates select="//node
                    [tag[@k = 'railway'and @v = 'station']]
                    [not(tag[@k = 'railway' and @v = 'abandoned'])]
                    [not(tag[@k = 'disused' and @v = 'yes'])]
                " />                
            </osm>
        </xsl:document>
    </xsl:template>
    
    <xsl:template match="node">
        <xsl:copy-of select="." />
    </xsl:template>
    
</xsl:stylesheet>
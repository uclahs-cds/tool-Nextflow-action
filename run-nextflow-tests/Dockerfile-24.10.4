ARG MAVEN_VERSION=3-amazoncorretto-8
ARG NEXTFLOW_VERSION=24.10.4

# Download dependencies using Maven
FROM maven:${MAVEN_VERSION} AS builder
COPY pom.xml /pom.xml
RUN mvn --batch-mode dependency:copy-dependencies -DoutputDirectory=/bljars

FROM josephburnett/jd:v1.8.1 AS jdimage

FROM nextflow/nextflow:${NEXTFLOW_VERSION}

COPY --from=builder /bljars /bljars
COPY --from=jdimage /jd /usr/local/bin/jd

# Modify the Nextflow launcher script to:
# 1. Append the new jars to the classpath
# 2. Replace the Nextflow entrypoint with groovy

# Generate a new Nextflow entrypoint
# 1. Run `NXF_CLASSPATH=... nextflow -v` to generate a new launcher script
# 2. Copy the contents of that script, swapping out the Nextflow entrypoint for
#    groovy
ENV testscript=/usr/local/bin/nextflow-config-test
ENV HACKED_NEXTFLOW=/tmp/hackednextflow

RUN yum install -y python3 findutils && \
    echo "#!/bin/bash" > "$testscript" && \
    echo -n "exec " >> "$testscript" && \
    awk 'NR==1 {print; print "exec() {"; print "    echo -n \"$@\""; print "    exit 0"; print "}" } NR>1' /usr/local/bin/nextflow > "$HACKED_NEXTFLOW" && \
    bash "$HACKED_NEXTFLOW" >> "$testscript" && \
    sed -i -e "s| -jar \([^ ]*\)| -cp \1$(find /bljars/ -not -name 'groovy-3*' -type f -printf ':%p')|" "$testscript" && \
    echo ' groovy.ui.GroovyMain "$@"' >> "$testscript" && \
    chmod +x "$testscript"

COPY betterconfig.groovy /usr/local/bltests/
COPY entry.py configtest.py utils.py /usr/local/bltests/
WORKDIR /mnt/pipeline

LABEL org.opencontainers.image.source=https://github.com/uclahs-cds/tool-Nextflow-action

ENTRYPOINT ["/usr/local/bltests/entry.py"]

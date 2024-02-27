ARG MAVEN_VERSION=3-amazoncorretto-8
ARG NEXTFLOW_VERSION=23.10.0

# Download dependencies using Maven
FROM maven:${MAVEN_VERSION} AS builder
COPY pom.xml /pom.xml
RUN mvn --batch-mode dependency:copy-dependencies -DoutputDirectory=/bljars

FROM nextflow/nextflow:${NEXTFLOW_VERSION}

COPY --from=builder /bljars /bljars

# Modify the Nextflow launcher script to:
# 1. Append the new jars to the classpath
# 2. Replace the Nextflow entrypoint with groovy

# Generate a new Nextflow entrypoint
# 1. Run `NXF_CLASSPATH=... nextflow -v` to generate a new launcher script
# 2. Copy the contents of that script, swapping out the Nextflow entrypoint for
#    groovy
ENV testscript=/usr/local/bin/nextflow-config-test
RUN yum install -y python3 && \
    echo "#!/bin/bash" > "$testscript" && \
    echo -n "exec " >> "$testscript" && \
    chmod +x "$testscript" && \
    NXF_OFFLINE=true \
        NXF_CLASSPATH=$(find /bljars/ -not -name 'groovy-3*' -type f -printf ":%p") \
        nextflow -v && \
    sed \
        $(find /.nextflow/tmp/launcher -name 'classpath-*' -printf '%T@\t%p\n' | sort -n | tail -n1 | cut -f2) \
        -e 's|"nextflow.cli.Launcher"|"groovy.ui.GroovyMain" "$@"|' >> "$testscript"

# Copy in the `nextflow config`-like groovy script
COPY betterconfig.groovy /usr/local/bltests/
COPY entry.py configtest.py utils.py /usr/local/bltests/
WORKDIR /mnt/pipeline

ENTRYPOINT ["/usr/local/bltests/entry.py"]

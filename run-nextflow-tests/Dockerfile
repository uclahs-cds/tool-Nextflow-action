ARG MAVEN_VERSION=3-amazoncorretto-8
ARG NEXTFLOW_VERSION=23.10.0

# Download dependencies using Maven
FROM maven:${MAVEN_VERSION} AS builder
COPY pom.xml /pom.xml
RUN mvn --batch-mode dependency:copy-dependencies -DoutputDirectory=/bljars

FROM nextflow/nextflow:${NEXTFLOW_VERSION}

COPY --from=builder /bljars /bljars

ARG NEXTFLOW_VERSION
# This should be fixed for a given version
ARG NEXTFLOW_MD5=acbb51bf66024671292c890f7d60ca8b
ENV NXF_LAUNCHER=/.nextflow/tmp/launcher/nextflow-one_${NEXTFLOW_VERSION}/buildkitsandbox
ENV NXF_DISABLE_CHECK_LATEST=true

# Modify the Nextflow launcher script to:
# 1. Append the new jars to the classpath
# 2. Replace the Nextflow entrypoint with groovy
RUN BL_JARS=$(find /bljars/ -not -name 'groovy-3*' -type f -printf ":%p") && \
    sed \
        -i \
        -e "s|\" \"nextflow.cli.Launcher\"|$BL_JARS\" \"groovy.ui.GroovyMain\"|" \
        ${NXF_LAUNCHER}/classpath-${NEXTFLOW_MD5}

# Copy in the `nextflow config`-like groovy script
COPY betterconfig.groovy /usr/local/bltests/
WORKDIR /mnt/pipeline

ENTRYPOINT ["nextflow"]
CMD ["/usr/local/bltests/betterconfig.groovy"]

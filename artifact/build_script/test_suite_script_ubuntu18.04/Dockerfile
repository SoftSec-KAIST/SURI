FROM suri_artifact_ubuntu18.04:v1.0

SHELL ["/bin/bash", "-c"]

COPY ./spec2006_image /spec_cpu2006
COPY ./script/case1_spec2006.cfg /spec_cpu2006/config/case1_bfd.cfg

# Set up SPEC CPU2006
RUN chmod -R +x /spec_cpu2006 && \
    /spec_cpu2006/install.sh -d /spec_cpu2006 -f && \
    cd /spec_cpu2006/ && \
    source shrc && \
    runspec --config=case1_bfd --action=build --tune=base all

COPY ./spec2017_image /spec_cpu2017
COPY ./script/case1_spec2017.cfg /spec_cpu2017/config/case1_bfd.cfg

# Set up SPEC CPU2017
RUN chmod -R +x /spec_cpu2017 && \
    /spec_cpu2017/install.sh -d /spec_cpu2017 -f && \
    cd /spec_cpu2017/ && \
    source shrc && \
    runcpu --config=case1_bfd --action=build --tune=base all

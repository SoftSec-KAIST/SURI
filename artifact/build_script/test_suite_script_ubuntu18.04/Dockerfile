FROM suri_artifact_ubuntu18.04:v1.0

COPY ./spec2006_image /spec_cpu2006

RUN /spec_cpu2006/install.sh -d /spec_cpu2006 -f

COPY ./script/case1_spec2006.cfg /spec_cpu2006/config/case1_bfd.cfg

SHELL ["/bin/bash", "-c"]

RUN cd /spec_cpu2006/ && \
    source shrc && \
    runspec --config=case1_bfd --action=build --tune=base all

COPY ./spec2017_image /spec_cpu2017

RUN /spec_cpu2017/install.sh -d /spec_cpu2017 -f

COPY ./script/case1_spec2017.cfg /spec_cpu2017/config/case1_bfd.cfg

RUN cd /spec_cpu2017/ && \
    source shrc && \
    runcpu --config=case1_bfd --action=build --tune=base all



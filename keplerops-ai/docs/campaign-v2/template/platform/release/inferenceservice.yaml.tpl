apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: orion-release-risk
  namespace: orion-runtime
  annotations:
    serving.kserve.io/deploymentMode: RawDeployment
    keplerops.lab/release-revision: __RELEASE_REVISION__
    keplerops.lab/model-digest: sha256:__MODEL_DIGEST__
    keplerops.lab/evaluation-digest: sha256:__EVALUATION_DIGEST__
spec:
  predictor:
    minReplicas: 1
    maxReplicas: 1
    containers:
      - name: kserve-container
        image: __IMAGE_REPOSITORY__@sha256:__IMAGE_DIGEST__
        imagePullPolicy: IfNotPresent
        ports:
          - {name: http1, containerPort: 8080, protocol: TCP}
        env:
          - {name: MODEL_NAME, value: orion-release-risk}
          - {name: MODEL_DIR, value: /models}
        readinessProbe:
          httpGet: {path: /health/ready, port: http1}
          initialDelaySeconds: 2
          periodSeconds: 5
        livenessProbe:
          httpGet: {path: /health/live, port: http1}
          initialDelaySeconds: 10
          periodSeconds: 10
        resources:
          requests: {cpu: 200m, memory: 256Mi}
          limits: {cpu: "2", memory: 1Gi}
        securityContext:
          allowPrivilegeEscalation: false
          capabilities: {drop: [ALL]}
          readOnlyRootFilesystem: true
          runAsNonRoot: true
          runAsUser: 65532
          seccompProfile: {type: RuntimeDefault}
        volumeMounts:
          - {name: tmp, mountPath: /tmp}
    volumes:
      - name: tmp
        emptyDir: {}

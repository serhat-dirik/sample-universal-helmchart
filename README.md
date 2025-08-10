
# One Chart to Rule Them All: A Deep Dive into Crafting Portable Helm Charts for Kubernetes and OpenShift

In the world of cloud-native development, Helm is the undisputed package manager for Kubernetes. It allows developers and operators to package, configure, and deploy applications onto any Kubernetes cluster. But "any" Kubernetes cluster is a broad term. While the Kubernetes API provides a standard, different distributions can have unique features and security postures.

Nowhere is this more apparent than with Red Hat OpenShift. As a fully CNCF-certified Kubernetes distribution, OpenShift guarantees API compatibility but builds upon that foundation with a hardened, enterprise-grade security model that can initially challenge unprepared Helm charts.[1]

This guide will walk you through the common challenges and best practices for creating a single, intelligent Helm chart that deploys flawlessly on both vanilla Kubernetes and Red Hat OpenShift. We'll provide a complete, production-ready example that you can publish to your own GitHub repository.

### The Core Challenge: Navigating OpenShift's Security Model

The most common hurdle developers face when deploying to OpenShift is its strict security-by-default stance. This is a feature, not a bug, designed to protect multi-tenant production environments. The primary mechanism for this is the **Security Context Constraint (SCC)**.

#### What are Security Context Constraints (SCCs)?

SCCs are an OpenShift-specific resource that controls the permissions a pod can request. They are a powerful enforcement layer that governs security-sensitive actions, such as:

  * Running as the root user (UID 0)
  * Running with a specific non-root user ID
  * Accessing host filesystems (`hostPath` volumes)
  * Using the host's network or process namespaces
  * Requesting privileged container status

By default, all user pods in OpenShift are assigned the highly restrictive `restricted-v2` SCC. This SCC forces containers to run with a randomly assigned, high-numbered UID, ignoring any `USER` directive in the `Dockerfile`. While this is a secure default, it can cause permission errors for applications that expect to run as a specific user.[2]

#### Common SCCs and Their Use Cases

While there are several built-in SCCs, a few are commonly encountered when trying to deploy applications not explicitly designed for OpenShift:

| SCC Name | What It Allows | Common Use Case |
| :---------------- | :--------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------- |
| **`restricted-v2`** | The most restrictive default. Runs pods with a random UID. Denies access to all host features and drops all Linux capabilities. | The default for all authenticated users. Well-behaved, cloud-native applications should aim to run here. |
| **`nonroot-v2`** | Allows the pod to run with any non-root UID, but the UID must be specified in the image or pod spec. | Applications that need to run as a specific non-root user (e.g., `USER 1001`) but do not require root privileges.[3] |
| **`anyuid`** | Allows the pod to run with *any* UID specified in the image, including root (UID 0). | The most common requirement for off-the-shelf images that are built to run as a specific user. This is our focus for the example.[2] |
| **`hostaccess`** | Allows access to the host network and PID namespaces. | Monitoring agents or other system-level tools that need to inspect the host node. |
| **`privileged`** | The least restrictive. Allows pods to run as privileged containers, effectively giving them root access on the host node. | System daemons or drivers (like the NVIDIA GPU Operator) that need deep host-level access. This should be granted with extreme caution. |

The key takeaway is that a portable Helm chart must be able to request the *permission to use* the appropriate SCC when on OpenShift, without breaking on other Kubernetes distributions that don't have SCCs.

### The Universal Solution: Conditional Logic with Helm

Helm's templating engine is the key to creating a portable chart. We can use conditional logic to detect the cluster's environment and generate OpenShift-specific resources only when needed. The most reliable way to detect an OpenShift cluster is to check for the existence of an OpenShift-specific API, like `route.openshift.io/v1`.

-----

### GitHub Example: Building a Portable Helm Chart

Here is the complete structure and content for a sample Helm chart. You can create these files and publish them to a new GitHub repository.

#### Project Structure
````
sample-universal-helmchart/ 
├── app/
│   ├── Dockerfile
│   └── main.py
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── \_helpers.tpl
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── serviceaccount.yaml
│   ├── openshift-scc-rbac.yaml
│   ├── ingress.yaml
│   ├── route.yaml
│   └── NOTES.txt
└── README.md
````

````

#### File Contents

**1. `app/main.py`**
A simple Python app that prints its UID in a loop.

```python
import os
import time

uid = os.getuid()
print(f"Hello from Universal App! My container is running as UID: {uid}")
print("I will print this message every 10 seconds. Use Ctrl+C to exit.")

while True:
    print(f"Still running as UID: {uid}...")
    time.sleep(10)
````

**2. `app/Dockerfile`**
This `Dockerfile` creates the `anyuid` problem by setting a specific non-root user.

```dockerfile
# Use a lightweight Python base image
FROM python:3.9-slim

# Create a non-root user with a specific UID
RUN useradd --uid 1001 --create-home appuser

# Set the working directory
WORKDIR /app

# Copy the application code
COPY main.py.

# Switch to the non-root user
USER 1001

# Command to run the application
CMD ["python", "main.py"]
```

**3. `Chart.yaml`**
This file contains the chart's metadata.

```yaml
apiVersion: v2
name: universal-chart
description: A Helm chart that works on both Kubernetes and OpenShift
type: application
version: 0.1.0
appVersion: "1.0.0"
```

**4. `values.yaml`**
This file defines the default configuration values.

```yaml
replicaCount: 1

image:
  # IMPORTANT: Replace this with the path to your own image after building and pushing it.
  # For example: 'quay.io/your-username/universal-app'
  # When using the OpenShift internal build, this will be something like:
  # image-registry.openshift-image-registry.svc:5000/universal-app-dev/universal-app
  repository: python
  pullPolicy: IfNotPresent
  # The tag should match the version of your application image
  tag: "3.9-slim"

serviceAccount:
  create: true
  name: ""

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: true
  className: ""
  annotations: {}
  hosts:
    - host: chart-example.local
      paths:
        - path: /
          pathType: ImplementationSpecific
  tls:

route:
  enabled: true
```

**5. `templates/_helpers.tpl`**
This is where we define our OpenShift detection logic and other standard helpers.

```go
{{/*
Create a helper to detect if the chart is running on OpenShift.
*/}}
{{- define "universal-chart.isOpenShift" -}}
  {{- if.Capabilities.APIVersions.Has "route.openshift.io/v1" -}}
    {{- true -}}
  {{- end -}}
{{- end -}}

{{/*
Define other standard helpers like fullname, chart name, etc.
This is typically generated by `helm create`.
*/}}
{{- define "universal-chart.fullname" -}}
{{- if.Values.fullnameOverride }}
{{-.Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default.Chart.Name.Values.nameOverride }}
{{- if contains $name.Release.Name }}
{{-.Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s".Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "universal-chart.name" -}}
{{- default.Chart.Name.Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "universal-chart.chart" -}}
{{- printf "%s-%s".Chart.Name.Chart.Version | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "universal-chart.labels" -}}
helm.sh/chart: {{ include "universal-chart.chart". }}
{{ include "universal-chart.selectorLabels". }}
{{- if.Chart.AppVersion }}
app.kubernetes.io/version: {{.Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{.Release.Service }}
{{- end }}

{{- define "universal-chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "universal-chart.name". }}
app.kubernetes.io/instance: {{.Release.Name }}
{{- end }}

{{- define "universal-chart.serviceAccountName" -}}
{{- if.Values.serviceAccount.create }}
{{- default (include "universal-chart.fullname".).Values.serviceAccount.name }}
{{- else }}
{{- default "default".Values.serviceAccount.name }}
{{- end }}
{{- end }}
```

**6. `templates/openshift-scc-rbac.yaml`**
This file contains the conditional RBAC resources to grant `anyuid` permissions. It will only be rendered when the chart is installed on an OpenShift cluster.

```yaml
{{- if include "universal-chart.isOpenShift". }}
# This Role grants permission to use the 'anyuid' Security Context Constraint.
# It is only created on OpenShift clusters.
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: {{ include "universal-chart.fullname". }}-anyuid-scc
  namespace: {{.Release.Namespace }}
  labels:
    {{- include "universal-chart.labels". | nindent 4 }}
rules:
- apiGroups:
  - security.openshift.io
  resourceNames:
  - anyuid
  resources:
  - securitycontextconstraints
  verbs:
  - use
---
# This RoleBinding applies the 'anyuid-scc' Role to the application's ServiceAccount.
# It is only created on OpenShift clusters.
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {{ include "universal-chart.fullname". }}-anyuid-scc
  namespace: {{.Release.Namespace }}
  labels:
    {{- include "universal-chart.labels". | nindent 4 }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: {{ include "universal-chart.fullname". }}-anyuid-scc
subjects:
- kind: ServiceAccount
  name: {{ include "universal-chart.serviceAccountName". }}
  namespace: {{.Release.Namespace }}
{{- end }}
```

**7. Other Template Files**
The remaining files (`deployment.yaml`, `service.yaml`, `serviceaccount.yaml`, `ingress.yaml`, `route.yaml`, `NOTES.txt`) are standard Helm templates. The key modifications are:

  * The `Deployment` must reference the `serviceAccountName`.
  * The `Ingress` and `Route` are mutually exclusive based on the `isOpenShift` helper.
  * The `NOTES.txt` informs the user what was created.

You can generate these with `helm create` and then modify them, or use the files from the previous response. The logic remains the same.

### Building and Deploying on OpenShift: A Practical Walkthrough

Now, let's see how to build our container image directly within OpenShift and deploy our universal chart.

**Step 1: Log in and Create a Project**
First, log in to your OpenShift cluster using the `oc` command-line tool and create a new project (which is an enhanced Kubernetes namespace).

```bash
# Log in to your OpenShift cluster
oc login --token=<your-token> --server=<your-api-server-url>

# Create a new project for our application
oc new-project universal-app-dev
```

**Step 2: Create a BuildConfig**
Instead of building our image externally, we can use an OpenShift `BuildConfig` to build it from our Git repository. This object defines the build strategy and source.[4]

```bash
# Create a BuildConfig that points to your Git repo and uses the Docker strategy
# Replace the URL with your forked repository URL
oc new-build [https://github.com/](https://github.com/)<your-username>/universal-chart.git \
  --context-dir=app \
  --name=universal-app \
  --strategy=docker
```

This command tells OpenShift to:

  * Look at the specified Git repository.
  * Use the `Dockerfile` located in the `app/` subdirectory (`--context-dir=app`).
  * Use the Docker build strategy.
  * Name the resulting image stream `universal-app`.

**Step 3: Start and Monitor the Build**
The `BuildConfig` will automatically trigger the first build. You can watch its progress.

```bash
# Watch the logs of the build
oc logs -f bc/universal-app
```

Once complete, OpenShift will have created an `ImageStream` in your project. This is a pointer to your container image in OpenShift's internal registry.[5]

**Step 4: Get the ImageStream Path**
To use this internal image in our Helm chart, we need its full path.

```bash
# Get the full path to the image in the internal registry
oc get is universal-app -o jsonpath='{.status.dockerImageRepository}'
```

The output will look something like this: `image-registry.openshift-image-registry.svc:5000/universal-app-dev/universal-app`

**Step 5: Configure and Deploy the Helm Chart**
Now, update your `values.yaml` file to use the internal image.

**`values.yaml` (updated section):**

```yaml
image:
  repository: image-registry.openshift-image-registry.svc:5000/universal-app-dev/universal-app
  pullPolicy: IfNotPresent
  tag: "latest"
```

Finally, install the Helm chart into your OpenShift project.

```bash
# Install the Helm chart from your local directory
helm install my-release. -n universal-app-dev
```

**Step 6: Verify the Deployment**
Check that the pod is running and that it started with the correct UID.

```bash
# Check the pod status
oc get pods

# Check the logs of the running pod
# Replace <pod-name> with the actual name of your pod
oc logs <pod-name>
```

If everything worked, you will see the output:
`Hello from Universal App! My container is running as UID: 1001`

This confirms that our conditional RBAC for the `anyuid` SCC was created and applied correctly, allowing the container to run with the user defined in the `Dockerfile`.

### Beyond Security: Other OpenShift Considerations

  * **Deployments vs. DeploymentConfigs:** You may see older OpenShift resources use a `DeploymentConfig` (DC). DCs are a legacy OpenShift object that predated the standard Kubernetes `Deployment`. **`DeploymentConfigs` were officially deprecated in OpenShift 4.14**.[6, 7] Modern, portable charts should **always** use the standard Kubernetes `Deployment` object.
  * **Builds and ImageStreams:** As we've shown, OpenShift has native objects for building images. While powerful, their use is optional.[8] A portable Helm chart can just as easily reference a pre-built image from an external registry like Quay.io or Docker Hub.[9]

### Conclusion

Creating a single Helm chart that works across the diverse Kubernetes landscape is not only possible but is a best practice for maintainability and distribution. By using Helm's conditional logic to detect the platform and apply specific configurations—like RBAC for OpenShift SCCs and choosing between an Ingress or a Route—you can build a robust, intelligent, and truly universal deployment package. This approach embraces the unique strengths of each platform without sacrificing portability.

```
```

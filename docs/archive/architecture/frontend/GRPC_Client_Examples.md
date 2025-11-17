# gRPC Client Code Examples

This document provides practical examples for making gRPC calls from both a Node.js backend (like the web-proxy) and a Vue.js frontend.

## Making gRPC Calls in Backend TypeScript (Node.js)

This pattern is used in the `web-proxy` to call other backend services.

### Non-Streaming Calls

```typescript
import { createClient } from "@connectrpc/connect";
import { createGrpcTransport } from "@connectrpc/connect-node";
import { MyService } from "./generated/my_service_pb.js";

// Create transport to a specific backend service
const transport = createGrpcTransport({
  baseUrl: "http://localhost:38001"
});

// Create a client for the target service
const client = createClient(MyService, transport);

// Make the call
async function getData(id: string) {
  try {
    const response = await client.getData({ id });
    console.log("Received:", response.data);
    return response;
  } catch (error) {
    console.error("gRPC call failed:", error);
    throw error;
  }
}
```

### Streaming Calls

```typescript
// Server streaming example
async function streamData() {
  const stream = client.streamData({ filter: "active" });

  for await (const response of stream) {
    console.log("Stream response:", response);
    // Process each response
  }
}

// Example with an abort controller for cancellation
async function streamWithCancel() {
  const controller = new AbortController();

  // Cancel the stream after 30 seconds
  setTimeout(() => controller.abort(), 30000);

  const stream = client.streamData(
    { filter: "active" },
    { signal: controller.signal }
  );

  try {
    for await (const response of stream) {
      console.log("Stream response:", response);
    }
  } catch (e) {
    if (e instanceof ConnectError && e.code === Code.Canceled) {
      console.log("Stream was cancelled");
    } else {
      throw e;
    }
  }
}
```

## Making gRPC Calls in Vue TypeScript (Frontend)

This pattern is used in the various Vue.js applications to communicate with the `web-proxy`.

### Setup in a Vue Component

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { createClient } from '@connectrpc/connect';
import { createConnectTransport } from '@connectrpc/connect-web';
import { MyService } from '@pipeline/proto-stubs';

// Create transport to the web-proxy, not the final backend service
const transport = createConnectTransport({
    baseUrl: `http://${window.location.hostname}:38106`, // Always target the web-proxy
});

// Create the client
const client = createClient(MyService, transport);

// Reactive data for the component
const data = ref<string>('');
const loading = ref(false);
const error = ref<Error | null>(null);
</script>
```

### Non-Streaming Calls in Vue

```vue
<script setup lang="ts">
// ... (setup from above)

// Example of fetching data when the component mounts
onMounted(async () => {
  loading.value = true;
  try {
    const response = await client.getData({ id: '123' });
    data.value = response.data;
  } catch (e) {
    error.value = e as Error;
    console.error('Failed to fetch data:', e);
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <v-card>
    <v-card-text>
      <div v-if="loading">Loading...</div>
      <div v-else-if="error" class="error">{{ error.message }}</div>
      <div v-else>{{ data }}</div>
    </v-card-text>
  </v-card>
</template>
```

### Streaming Calls in Vue

```vue
<script setup lang="ts">
import { ref, onUnmounted } from 'vue';
// ... (setup from above)

const streamData = ref<Array<any>>([]);
const isStreaming = ref(false);
let abortController: AbortController | null = null;

const startStream = async () => {
  if (isStreaming.value) return;

  isStreaming.value = true;
  streamData.value = [];
  abortController = new AbortController();

  try {
    const stream = client.streamData(
      { filter: 'active' },
      { signal: abortController.signal }
    );

    for await (const response of stream) {
      streamData.value.push(response);
      // Vue automatically updates the UI
    }
  } catch (e) {
    if (e instanceof ConnectError && e.code !== Code.Canceled) {
      console.error('Stream error:', e);
    }
  } finally {
    isStreaming.value = false;
  }
};

const stopStream = () => {
  abortController?.abort();
};

// Clean up the stream when the component is unmounted
onUnmounted(() => {
  stopStream();
});
</script>

<template>
  <v-card>
    <v-card-title>Live Stream</v-card-title>
    <v-card-text>
      <v-list>
        <v-list-item v-for="(item, index) in streamData" :key="index">
          {{ item }}
        </v-list-item>
      </v-list>
    </v-card-text>
    <v-card-actions>
      <v-btn v-if="!isStreaming" @click="startStream">Start</v-btn>
      <v-btn v-else @click="stopStream">Stop</v-btn>
    </v-card-actions>
  </v-card>
</template>
```

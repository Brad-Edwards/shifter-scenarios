"use strict";

const CHANNEL_LABEL = "keplerops-live-capture-v1";
const elements = {
  participantId: document.getElementById("participant-id"),
  rangeId: document.getElementById("range-id"),
  initToken: document.getElementById("init-token"),
  start: document.getElementById("start"),
  stop: document.getElementById("stop"),
  control: document.getElementById("capture-control"),
  attack: document.getElementById("capture-attack"),
  preview: document.getElementById("preview"),
  status: document.getElementById("status"),
  pairStatus: document.getElementById("pair-status"),
};

let peer = null;
let channel = null;
let mediaStream = null;
let session = null;
let activePairId = null;
let pendingRole = null;

function setStatus(state, message) {
  elements.status.dataset.state = state;
  elements.status.textContent = message;
}

function setButtons({ connected = false, control = false, attack = false } = {}) {
  elements.start.disabled = connected;
  elements.stop.disabled = !connected;
  elements.control.disabled = !control;
  elements.attack.disabled = !attack;
}

async function waitForIceGatheringComplete(connection) {
  if (connection.iceGatheringState === "complete") {
    return;
  }
  await new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      connection.removeEventListener("icegatheringstatechange", checkState);
      reject(new Error("ICE candidate gathering timed out"));
    }, 10000);
    function checkState() {
      if (connection.iceGatheringState === "complete") {
        window.clearTimeout(timeout);
        connection.removeEventListener("icegatheringstatechange", checkState);
        resolve();
      }
    }
    connection.addEventListener("icegatheringstatechange", checkState);
  });
}

async function initiateSession() {
  const response = await fetch("/v1/sessions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${elements.initToken.value}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      participant_id: elements.participantId.value,
      range_id: elements.rangeId.value,
      client_timestamp_ms: Date.now(),
    }),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || "Session initiation failed");
  }
  if (body.data_channel_label !== CHANNEL_LABEL) {
    throw new Error("Server capture protocol does not match this client");
  }
  return body;
}

function configureDataChannel(dataChannel) {
  dataChannel.addEventListener("open", () => {
    setButtons({ connected: true, control: true, attack: false });
    setStatus("connected", "Live WebRTC camera connected. Ready for a control frame.");
  });
  dataChannel.addEventListener("close", () => {
    setButtons();
    setStatus("closed", "The capture data channel closed.");
  });
  dataChannel.addEventListener("message", (event) => {
    let result;
    try {
      result = JSON.parse(event.data);
    } catch (error) {
      setStatus("error", `Unreadable server message: ${error.message}`);
      return;
    }
    if (result.type !== "capture-result") {
      return;
    }
    const completedRole = pendingRole;
    pendingRole = null;
    if (!result.ok) {
      setButtons({ connected: true, control: completedRole === "control", attack: completedRole === "attack" });
      setStatus("error", result.reason || "Live frame capture failed");
      return;
    }
    if (completedRole === "control") {
      elements.pairStatus.textContent = `Pair ${activePairId}: control retained; attack frame required.`;
      setButtons({ connected: true, control: false, attack: true });
    } else {
      elements.pairStatus.textContent = `Pair ${activePairId}: control and attack frames retained.`;
      activePairId = null;
      setButtons({ connected: true, control: true, attack: false });
    }
    setStatus("captured", `${result.role} frame ${result.frame_id} classified by platform-ml.`);
  });
}

async function start() {
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    setStatus("error", "Camera access requires HTTPS or a localhost origin.");
    return;
  }
  if (!elements.initToken.value) {
    setStatus("error", "Enter the authenticated session initiation token.");
    return;
  }
  setButtons({ connected: true });
  setStatus("starting", "Requesting explicit browser camera permission...");
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        width: { ideal: 320, max: 640 },
        height: { ideal: 240, max: 480 },
        frameRate: { ideal: 5, max: 5 },
        facingMode: { ideal: "environment" },
      },
    });
    elements.preview.srcObject = mediaStream;
    session = await initiateSession();
    peer = new RTCPeerConnection({ iceServers: [] });
    channel = peer.createDataChannel(CHANNEL_LABEL, { ordered: true });
    configureDataChannel(channel);
    mediaStream.getVideoTracks().forEach((track) => peer.addTrack(track, mediaStream));
    peer.addEventListener("connectionstatechange", () => {
      if (["failed", "disconnected"].includes(peer.connectionState)) {
        setStatus("error", `WebRTC connection ${peer.connectionState}.`);
      }
    });
    const offer = await peer.createOffer();
    await peer.setLocalDescription(offer);
    await waitForIceGatheringComplete(peer);
    const response = await fetch(session.offer_url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.session_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(peer.localDescription),
    });
    const answer = await response.json();
    if (!response.ok) {
      throw new Error(answer.detail || "WebRTC signaling failed");
    }
    await peer.setRemoteDescription(answer);
    setStatus("negotiating", "WebRTC negotiated; waiting for the authenticated data channel.");
  } catch (error) {
    setStatus("error", error?.message || "Live camera start failed");
    await stop(false);
  }
}

function sendCapture(role) {
  if (channel?.readyState !== "open" || pendingRole !== null) {
    setStatus("error", "The live capture data channel is not ready.");
    return;
  }
  if (role === "control") {
    activePairId = `pair-${Date.now()}-${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`;
  }
  if (!activePairId) {
    setStatus("error", "A control frame must start the pair.");
    return;
  }
  pendingRole = role;
  setButtons({ connected: true });
  channel.send(JSON.stringify({
    type: "capture",
    pair_id: activePairId,
    role,
    client_timestamp_ms: Date.now(),
    nonce: crypto.randomUUID().replaceAll("-", ""),
  }));
  setStatus("capturing", `Waiting for the next fresh live ${role} frame...`);
}

async function stop(notifyServer = true) {
  const closingSession = session;
  session = null;
  activePairId = null;
  pendingRole = null;
  if (notifyServer && closingSession) {
    try {
      await fetch(`/v1/sessions/${closingSession.session_id}/close`, {
        method: "POST",
        headers: { Authorization: `Bearer ${closingSession.session_token}` },
      });
    } catch (_error) {
      // The local camera must still be released if the signaling service is gone.
    }
  }
  if (channel) {
    channel.close();
    channel = null;
  }
  if (peer) {
    peer.close();
    peer = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
  elements.preview.srcObject = null;
  elements.pairStatus.textContent = "No active pair.";
  setButtons();
  if (notifyServer) {
    setStatus("closed", "Session closed and local camera released.");
  }
}

elements.start.addEventListener("click", start);
elements.stop.addEventListener("click", () => stop(true));
elements.control.addEventListener("click", () => sendCapture("control"));
elements.attack.addEventListener("click", () => sendCapture("attack"));
window.addEventListener("pagehide", () => stop(false));

window.kepleropsCamera = {
  start,
  stop,
  captureControl: () => sendCapture("control"),
  captureAttack: () => sendCapture("attack"),
  getState: () => elements.status.dataset.state,
};

package main

import (
	"encoding/json"
	"fmt"
	"os"
)

var buildID = "unset"

type description struct {
	Name       string `json:"name"`
	BuildID    string `json:"build_id"`
	Target     string `json:"target"`
	ConfigPath string `json:"config_path"`
	KeyMethod  string `json:"key_method"`
	KeySalt    string `json:"key_salt"`
	KeyInfo    string `json:"key_info"`
	Cipher     string `json:"cipher"`
	AAD        string `json:"aad"`
}

func main() {
	if len(os.Args) != 2 || os.Args[1] != "describe" {
		fmt.Fprintln(os.Stderr, "usage: collector-crr describe")
		os.Exit(2)
	}
	value := description{
		Name:       "collector-crr",
		BuildID:    buildID,
		Target:     "linux/amd64",
		ConfigPath: "config/collector.yaml.enc",
		KeyMethod:  "HKDF-SHA256",
		KeySalt:    "COL-CRR-2019",
		KeyInfo:    "collector-config/v3",
		Cipher:     "AES-256-GCM",
		AAD:        "config/collector.yaml",
	}
	encoded, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	fmt.Println(string(encoded))
}

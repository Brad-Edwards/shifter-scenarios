/*
 * Copyright 2026 KeplerOps AI Systems
 * SPDX-License-Identifier: Apache-2.0
 */
package com.keplerops.orion;

import android.app.Activity;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public final class MainActivity extends Activity {
    public static final String API_ORIGIN = "https://preview.keplerops.lab/";
    public static final String API_PATH = "/api/analyze";
    public static final String MODEL_FAMILY = "release-risk";
    public static final String MODEL_SERVICE = "orion-release-risk";
    private WebView view;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);

        view = new WebView(this);
        view.getSettings().setJavaScriptEnabled(true);
        view.getSettings().setAllowFileAccess(false);
        view.getSettings().setAllowContentAccess(false);
        view.setWebViewClient(new WebViewClient() {
            private boolean isPreview(Uri uri) {
                return "https".equals(uri.getScheme())
                    && "preview.keplerops.lab".equals(uri.getHost());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView webView, WebResourceRequest request) {
                return !isPreview(request.getUrl());
            }

            @Override
            @SuppressWarnings("deprecation")
            public boolean shouldOverrideUrlLoading(WebView webView, String url) {
                return !isPreview(Uri.parse(url));
            }
        });
        view.loadUrl(API_ORIGIN);
        setContentView(view);
    }

    @Override
    public void onBackPressed() {
        if (view.canGoBack()) {
            view.goBack();
            return;
        }
        super.onBackPressed();
    }
}

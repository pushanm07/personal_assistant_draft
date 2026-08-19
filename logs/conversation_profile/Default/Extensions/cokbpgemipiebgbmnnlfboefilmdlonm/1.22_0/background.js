// Trellix LLC, SOFTWARE LICENSE TERMS
// Copyright (c) 2022 Trellix LLC. All rights reserved.
//
// THIS SOFTWARE CONTAINS CONFIDENTIAL INFORMATION AND TRADE SECRETS OF Trellix LLC.  
// USE, DISCLOSURE OR REPRODUCTION IS PROHIBITED WITHOUT THE PRIOR
// EXPRESS WRITTEN PERMISSION OF Trellix LLC.
//
// NOTICE TO ALL USERS: CAREFULLY READ THE APPROPRIATE LEGAL AGREEMENT CORRESPONDING TO 
// THE LICENSE YOU PURCHASED, WHICH SETS FORTH THE GENERAL TERMS AND CONDITIONS FOR THE 
// USE OF THE LICENSED SOFTWARE. IF YOU DO NOT KNOW WHICH TYPE OF LICENSE YOU HAVE ACQUIRED, 
// PLEASE CONSULT THE SALES AND OTHER RELATED LICENSE GRANT OR PURCHASE ORDER DOCUMENTS 
// THAT ACCOMPANY YOUR SOFTWARE PACKAGING OR THAT YOU HAVE RECEIVED SEPARATELY AS PART OF 
// THE PURCHASE (AS A BOOKLET, A FILE ON THE PRODUCT CD, OR A FILE AVAILABLE ON THE WEBSITE FROM 
// WHICH YOU DOWNLOADED THE SOFTWARE PACKAGE). IF YOU DO NOT AGREE TO ALL OF THE TERMS SET FORTH 
// IN THE AGREEMENT, DO NOT INSTALL THE SOFTWARE.

'use strict';

var port = null;
var nmConfig;

function connectPort() {
    /*console.log("connecting to native host");*/
    port = chrome.runtime.connectNative('com.trellix.dlp_native_messaging_host');
    port.onDisconnect.addListener(portOnDisconnect);
}

function portOnDisconnect(port) {
    /*console.log("disconnected from native host - " + port.error);*/
    connectPort();
}

connectPort();

function loadDataFromStg()
{
   chrome.storage.local.get(["nmConfig"], (result) => {
   nmConfig = result.nmConfig;
   console.log('Loaded Data: ' + JSON.stringify(result));
});

}

loadDataFromStg();

port.onMessage.addListener(function (msg) {
		if (msg.pagetext) {
			chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
				if(tabs && tabs.length > 0){
					/**
					 * A tab may have multiple iframes inside it and we inject content script into each one of them
					 * which are in their own execution environment. For printer protection we need to get the content
					 * of all the frames in a tab and so, this page text request needs to be processed by all frames.
					 * Here, we combine the responses and send them as a single response to the native app.
					 */
					const tabId = tabs[0].id;
					chrome.webNavigation.getAllFrames(
					{ tabId: tabId },
					async function (frames) {
						const responses = [];
						if (frames && frames.length > 0) {
							try{
								let response = await chrome.tabs.sendMessage(tabs[0].id, msg, { frameId: frames[0].frameId });
								if (!response.pagetext.url) {
									response.pagetext.url = decodeURIComponent(tabs[0].url);
								}
								if (isSpecficUrl(response.pagetext.url)) {
									if (response.pagetext.window_location) {
										response.pagetext.url = decodeURIComponent(response.pagetext.window_location);
									}
								}
								responses.push(response);
							}
							catch(e)
							{
								port.postMessage({ 'pagetext': { 'id': msg.pagetext.id, 'text': "", 'url': decodeURIComponent(tabs[0].url) } });
								return;
							}
							
							for (var i = 1; i < frames.length ; i++) {
								try
								{
									let response = await chrome.tabs.sendMessage(tabs[0].id, msg, { frameId: frames[i].frameId });
									responses[0].pagetext.text += "\n" + response.pagetext.text;
								}
								catch(e)
								{
									/*console.log("Ignoring this frame because of the errors");*/
								}
							}
							if(responses.length > 0)
								port.postMessage(responses[0]);
						}
					});
				}
			});
		}
		if (msg.nmConfig) {
		nmConfig = msg.nmConfig;
		console.log('received data: ' + JSON.stringify(msg.nmConfig));
		chrome.storage.local.set({"nmConfig": msg.nmConfig}, () => {
		console.log('stored data: ' + JSON.stringify(msg.nmConfig));
		});
		
	}
}
);

chrome.runtime.onMessage.addListener(function (msg, sender) {
	if (msg.inputfile || msg.fileDropChangeEvent) {
		var s = Object.assign({}, msg, { 'url': decodeURIComponent(msg.urlFromCS) });
		
		port.postMessage(s);
	}
});


function forEachTabs(tabs) {
	for (const tab of tabs) {
		if (isCStoInject(tab.url)) {
			
			chrome.scripting.executeScript(
				{
					target: { tabId: tab.id, allFrames: true },
					files: ['content.js'],
				});

		}
	}
}


chrome.tabs.query({}).then(forEachTabs);


function isBlockUrl(details) {

    if ((!nmConfig) || (!nmConfig.httpHandlerEnabled) || (!nmConfig.blockedWebUriList) || (nmConfig.blockedWebUriList.length == 0)) {
        return false;
    }
    let curUrl = details.url;
    let decodedurl = decodeURIComponent(curUrl);
    const parsedUrl = new URL(decodedurl);
    let hostname = parsedUrl.hostname ? parsedUrl.hostname.toLowerCase() : "";
    let protocol = parsedUrl.protocol ? parsedUrl.protocol.toLowerCase() : "";
    let port = parsedUrl.port ? parsedUrl.port.toLowerCase() : "";
    let path = parsedUrl.pathname ? parsedUrl.pathname.toLowerCase() : "";
    let query = parsedUrl.search ? parsedUrl.search.toLowerCase() : "";

    if (protocol.endsWith(":")) {
        protocol = protocol.slice(0, protocol.length - 1);
    }


    for (let index in nmConfig.blockedWebUriList) {

        let failedMatch = false;
        let anyMatch = false;
        let item = nmConfig.blockedWebUriList[index];

        if (item.hostname && item.hostname.length && hostname.length) {
            if (hostname.endsWith(item.hostname)) {
                anyMatch = true;
                if (hostname.length > item.hostname.length) {
                    if (hostname.at(-(item.hostname.length + 1)) != ".") {
                        failedMatch = true;
                    }
                }
            } else {
                failedMatch = true;
            }
        }

        if (item.protocol && item.protocol.length && protocol.length) {
            if (protocol == item.protocol) {
                anyMatch = true;
            } else {
                failedMatch = true;
            }
        }


        if (item.path && item.path.length && path.length) {
            if (path == item.path) {
                anyMatch = true;
            } else {
                failedMatch = true;
            }
        }

        if (item.query && item.query.length && query.length) {
            if (query == item.query) {
                anyMatch = true;
            } else {
                failedMatch = true;
            }
        }

        if (item.port && item.port.length && port.length) {
            if (port == item.port) {
                anyMatch = true;
            } else {
                failedMatch = true;
            }
        }

        if (anyMatch) {
            if (failedMatch) {
                return false;
            }
            return true;
        }
    }

    return false;

}

function isChromeInternalUrl(url) {

	return (url?.startsWith("chrome://"));

}

function isSpecficUrl(url) {

	const urlsStartPattern = ["about:", "data:", "blob:", "filesystem:"];

	for (const urlIt of urlsStartPattern) {
		if (url.startsWith(urlIt)) {
			return true;
		}
	}
	return false;

}


function isCStoInject(url) {

	return !(isChromeInternalUrl(url));

}


function isFileUrl(url) {

	return (url?.startsWith("file:"));

}

function geCorrectUrl(tabid, urlFromCS, fun, getFromCS = true) {

	
	let goturl = false;
	if (getFromCS) {
		if (isSpecficUrl(urlFromCS)) {
			goturl = true;
			chrome.tabs.sendMessage(tabid, { urlFromCS: "true" }).then((response) => {
				if (response && response.windowLocation && response.windowLocation.url) {
					fun(response.windowLocation.url);
					
				}
			}).catch(function (error) {
				
				fun(urlFromCS);
			});
		}
	}
	if (!goturl) {
		
		fun(urlFromCS);
	}
}

function injectCStoTab(tabinfo) {

	chrome.tabs.sendMessage(tabinfo.tabid, { isThere: true }).then((response) => {
		if ((!response) || (!response.yes)) {
			
			chrome.scripting.executeScript(
				{
					target: { tabId: tabinfo.tabid, allFrames: true },
					files: ['content.js'],
				});
		}
	}).catch(function (error) {
		
		chrome.scripting.executeScript(
			{
				target: { tabId: tabinfo.tabid, allFrames: true },
				files: ['content.js'],
			});
	});

}
var requestsMap = new Map();

chrome.webRequest.onBeforeRequest.addListener(function (details) {
	let msg = { "url": details.url, "files": [] };
	if ('requestBody' in details && 'raw' in details.requestBody) {
		details.requestBody.raw.forEach(element => {
			if ('file' in element) {
				
				msg.files.push(element.file)
			}
		});
	}

	if (0 == msg.files.length) {
		if (details.method == "POST" || details.method == "PUT" || details.method == "PATCH") {

			let payload = JSON.stringify(details);

			if (details.requestBody && details.requestBody.raw) {
				for (var i = 0; i < details.requestBody.raw.length; ++i) {
					if (details.requestBody.raw[i].bytes) {
						var dv = new DataView(details.requestBody.raw[i].bytes);
						for (var j = 0; j < dv.byteLength; ++j) {
							payload += (String.fromCharCode(dv.getInt8(j)));
						}
					}
				}
			}
			requestsMap.set(details.requestId, payload);
		}
	}

	try{
		let urlBlocked = isBlockUrl(details);
		if(urlBlocked){
		console.log("blocking-" + details.url);
		port.postMessage({ 'onBeforeRequest': { 'blockedurl': details.url } });	
		}
		return { cancel: urlBlocked };
	}
	catch(err){
		
	}
	return { cancel: false };
},
	{ urls: ["<all_urls>"] },
	["requestBody", "blocking"]
);

chrome.webRequest.onSendHeaders.addListener(function (details) {
	var payload = requestsMap.get(details.requestId);
	if (payload) {
		for (var i = 0; i < details.requestHeaders.length; i++) {
			if (details.requestHeaders[i].name == "Content-Type") {
				if (details.requestHeaders[i].value == "application/x-www-form-urlencoded") {
					payload = decodeURIComponent(payload);
				}
				break;
			}
		}

		port.postMessage({ 'post': { 'url': decodeURIComponent(details.url), 'payload': payload } });
	}
},
	{ urls: ["<all_urls>"] },
	["requestHeaders"]
);

chrome.webRequest.onErrorOccurred.addListener(function (details) {
	requestsMap.delete(details.requestId);
},
	{ urls: ["<all_urls>"] }
);

chrome.webRequest.onCompleted.addListener(function (details) {
	requestsMap.delete(details.requestId);
},
	{ urls: ["<all_urls>"] }
);

chrome.tabs.onActivated.addListener(function (activeInfo) {
	chrome.tabs.get(activeInfo.tabId, function (tab) {
		if (tab.url) {
			var tabinfo = {};
			tabinfo.url = tab.url;
			tabinfo.tabid = tab.id;

			if (isCStoInject(tabinfo.url)) {
				
				injectCStoTab(tabinfo);

			}
			geCorrectUrl(activeInfo.tabId, tab.url, function (urlFromCS) {
				if (!isChromeInternalUrl(urlFromCS)) {
					port.postMessage({ 'activeurl': { 'id': tab.id.toString() + "-" + tab.windowId.toString(), 'url': decodeURIComponent(urlFromCS), 'state': "onActivated" } });
				}
			});
		}
	});
});

chrome.windows.onFocusChanged.addListener(function () {
	chrome.tabs.query({ currentWindow: true, lastFocusedWindow: true, active: true }, function (tabsArr) {
		if (0 < tabsArr.length && tabsArr[0].url) {
			
			var tabinfo = {};
			tabinfo.url = tabsArr[0].url;
			tabinfo.tabid = tabsArr[0].id;

			if (isCStoInject(tabinfo.url)) {
				
				injectCStoTab(tabinfo);
			}

			
			geCorrectUrl(tabinfo.tabid, tabinfo.url, function (urlFromCS) {
				if (!isChromeInternalUrl(urlFromCS)) {
					
					port.postMessage({ 'activeurl': { 'id': tabsArr[0].id.toString() + "-" + tabsArr[0].windowId.toString(), 'url': decodeURIComponent(urlFromCS), 'state': "onFocusChanged" } });
					
				}
			});

		}
	});
});


chrome.tabs.onUpdated.addListener(function (tabId, changeInfo, tab) {
	
	
	if (tab && tab.url && tab.active) {
		
		geCorrectUrl(tab.id, tab.url, function (urlFromCS) {
			port.postMessage({ 'activeurl': { 'id': tab.id.toString() + "-" + tab.windowId.toString(), 'url': decodeURIComponent(urlFromCS), 'state': "onUpdated" } });
		});
	}

});


chrome.webNavigation.onHistoryStateUpdated.addListener(
	function (details) {
		
		if (details.url && details.tabId) {

			var tabinfo = {};
			tabinfo.url = details.url;
			tabinfo.tabid = details.tabId;

			if (isCStoInject(tabinfo.url)) {
				

				injectCStoTab(tabinfo);

			}
			
			geCorrectUrl(tabinfo.tabid, tabinfo.url, function (urlFromCS) {
				if (!isChromeInternalUrl(urlFromCS)) {
					
					port.postMessage({ 'activeurl': { 'id': tabinfo.tabid.toString(), 'url': decodeURIComponent(urlFromCS), 'state': "onHistoryStateUpdated" } });
					
				}
			});
		}

	});

chrome.tabs.onRemoved.addListener(function (tabId, removeInfo) {
	
	port.postMessage({ 'urlremove': { 'id': tabId.toString() + "-" + removeInfo.windowId.toString() } });
}
);



chrome.webNavigation.onCommitted.addListener(function (details) {
	port.postMessage({ 'onCommitted': JSON.stringify(details) });
}
);

chrome.webNavigation.onBeforeNavigate.addListener(function (details) {
	port.postMessage({ 'onBeforeNavigate': JSON.stringify(details) });
}
);

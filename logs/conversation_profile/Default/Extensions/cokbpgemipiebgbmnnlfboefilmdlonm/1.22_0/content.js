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

chrome.runtime.onMessage.addListener(
    function (msg, sender, sendResponse) {
        if (msg.pagetext) {
            sendResponse({ 'pagetext': { 'window_location': window.location.href, 'id': msg.pagetext.id, 'text': document.body.innerText } });
        }
        if (msg.urlFromCS) {
            var urlFromCS = window.location.href;
            
            sendResponse({ 'windowLocation': { 'url': urlFromCS } });
        }

        if (msg.isThere) {
            
            sendResponse({ 'yes': true });
        }
    }
);

var pageFiles = new Set();

function cacheFile(file) {
    var fName = file.name;
    var fSize = file.size;
    var fModification = file.lastModified;

    pageFiles.add(file)

    
    
    chrome.runtime.sendMessage({ 'inputfile': { name: fName, size: fSize, modification: fModification }, urlFromCS: window.location.href });
}

document.addEventListener('click', function (e) {

    for (const file of pageFiles) {
        cacheFile(file);
    }
}, false);




function actOnInputFile(e) {
    try {
        if (!e) {
            return;
        }

        // Use composedPath to get the original event target, even if it's in a Shadow DOM.
        // composedPath()[0] is the element that originally dispatched the event.
        // Safely extract event target (with backward compatibility)
        const path = (typeof e.composedPath === "function") ? e.composedPath() : [];
        const originalTarget = path.length > 0 ? path[0] : e.target;

        if (!originalTarget) {
            return;
        }

        // Ensure the event target is an <input type="file">
        const tagName = originalTarget.tagName?.toLowerCase();
        const inputType = originalTarget.type?.toLowerCase();
        if (tagName !== "input" || inputType !== "file") {
            return;
        }

        const files = originalTarget.files;
        if (!files || files.length === 0) {
            return;
        }

        const filelistStr = Array.from(files)
            .filter(file => file && typeof file.name === "string" && file.name.length > 0)
            .map(file => file.name)
            .join(":");

        if (!filelistStr) {
            return;
        }

        chrome.runtime.sendMessage({ 'fileDropChangeEvent': { evDataFileList: true, evData: filelistStr }, urlFromCS: window.location.href });

    } catch (err) {
    }
}

function onInputInput(e) {

    actOnInputFile(e);

}


document.removeEventListener('input', onInputInput, true);
document.addEventListener('input', onInputInput, true);


document.addEventListener('change', function (e) {

    actOnInputFile(e);

    if (e.target && e.target.files) {
        for (let i = 0; i < e.target.files.length; i++) {
            cacheFile(e.target.files[i]);
        }
    }
}, true);


function readDirectory(directory) {
    var dirReader = directory.createReader();

    var readEntries = function () {
        dirReader.readEntries(function (entries) {
            for (var i = 0; i < entries.length; i++) {
                if (entries[i].isDirectory) {
                    readDirectory(entries[i]);
                }
                else {
                    entries[i].file(function (file) {
                        cacheFile(file);
                    }
                    );
                }
            }

            if (entries.length > 0) {
                readEntries();
            }
        });
    }

    readEntries();
}

document.addEventListener('drop', function (e) {
    try {

        var files = e.dataTransfer ? e.dataTransfer.files : null;

        if (!files) {
            return;
        }

        var filelistStr = "";
        for (var i = 0 && files != null; i < files.length; i++) {
            var file = files.item(i);
            if (filelistStr.length) {
                filelistStr += ":";
            }
            filelistStr += file.name;
        }
        if (filelistStr.length) {
            chrome.runtime.sendMessage({ 'fileDropChangeEvent': { evDataFileList: true, evData: filelistStr }, urlFromCS: window.location.href });
        }

        for (var i = 0; i < e.dataTransfer.items.length; i++) {
            if (typeof e.dataTransfer.items[i].webkitGetAsEntry !== "function") {
                cacheFile(e.dataTransfer.items[i].getAsFile());
                continue;
            }

            var entry = e.dataTransfer.items[i].webkitGetAsEntry();
            if (entry && entry.isDirectory) {
                readDirectory(entry);
            }
            else {
                cacheFile(e.dataTransfer.items[i].getAsFile());
            }
        }
    } catch (err) {

    }

}, true);


function allowedNode(elem) {
    let allowedNode = elem.nodeType == 1 || elem.nodeType == 5 || elem.nodeType == 6 || elem.nodeType == 9 || elem.nodeType == 11;
    return allowedNode;
}


function onSDOMInputFileChange(e) {

    actOnInputFile(e);

}


function addLsitenerOnInputListenerItem(elem, enforced) {
    let addListener = false;
    
    let input = elem.tagName && elem.tagName.toLowerCase() == "input" && elem.type && elem.type.toLowerCase() == "file";
    if (input) {
        addListener = true;
    }
    if (addListener) {
        elem.removeEventListener('change', onSDOMInputFileChange);
        elem.addEventListener('change', onSDOMInputFileChange, true);
        elem.removeEventListener('input', onSDOMInputFileChange);
        elem.addEventListener('input', onSDOMInputFileChange, true);
    }
}

function addListenerOnSDOMfileInput(elem) {

    let fileInputList = elem.childNodes;
    if (fileInputList && fileInputList.length) {
        let addListener = false;
        for (let i = 0; i < fileInputList.length; i++) {
            let elemChild = fileInputList[i];
            if (!allowedNode(elemChild)) {
                continue;
            }

            addLsitenerOnInputListenerItem(elemChild, false);
        }

    }

    if (allowedNode(elem)) {
        addLsitenerOnInputListenerItem(elem, false);
    }
}


function attachListenerToSDOMTree(elem, shadowRootParent) {

    let childlist = elem.childNodes;
    if ((!childlist || childlist.length == 0)) {

        return;
    }
    for (let i = 0; i < childlist.length; i++) {
        let elemChild = childlist[i];
        if (elemChild.shadowRoot) {

            elemChild = elemChild.shadowRoot;
            shadowRootParent = true;
        }

        if (shadowRootParent) {

            if (allowedNode(elemChild)) {
                addListenerOnSDOMfileInput(elemChild);
            }
        }

        if (allowedNode(elemChild)) {
            attachListenerToSDOMTree(elemChild, shadowRootParent);
        }
    }
}

function addListenerToSDOMinputTypeParent() {

    let childlist = document.body.childNodes;
    if (childlist) {
        for (let i = 0; i < childlist.length; i++) {
            let elemChild = childlist[i];
            attachListenerToSDOMTree(elemChild, (elemChild.shadowRoot != null));
        }
    }
}


window.addEventListener('load', (event) => {
    addListenerToSDOMinputTypeParent();
});


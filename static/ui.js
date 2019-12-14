document.addEventListener('DOMContentLoaded', function () { 

  const flashes = document.getElementById('flashes')
  if (flashes) {
    flashes.style.opacity = 1
    setTimeout(() => { flashes.style.opacity = 0 }, 3000)
  }

  // #highlight is an absolutely-positioned div with partial opacity
  // which covers the entire viewport and is not displayed by default. These
  // functions can be used to 'highlight' the viewport, to indicate that it is
  // ready to receive a dropped file, by making #highlight visible.
  const overlay = document.getElementById('drag-drop-overlay')
  const highlight = function (event)  {
    event.preventDefault()
    overlay.classList.add('active')
  } 
  const unhighlight = function (event) {
    if (event) event.preventDefault()
    overlay.classList.remove('active')
  }

  // This handler is used to accept (upload) a dropped file.
  const accept = function (event) {
    event.preventDefault()
    unhighlight()
    const files = event.dataTransfer.files
    for (var i = 0; i < files.length; i++) {
      upload(files[i])
      console.dir(files[i].name, files[i].size / 1024, files[i].type)
    }
  }

  // Adds a new notification toast for a new file upload, and updates the
  // progress indicator as the file uploads
  const upload = function (file) {
    //Create a new row in the table
    var firstRow = document.querySelector('tbody tr')
    var newRow = document.createElement('TR')
    var newCell = document.createElement('TD')
    newCell.colSpan = 9
    newCell.innerText = file.name
    firstRow.parentNode.insertBefore(newRow, firstRow)
    newRow.appendChild(newCell)

    // Create progress indicator
    const size = Math.round(file.size / 1024).toLocaleString() + ' KiB'
    var progressIndicator = document.createElement('div')
    progressIndicator.className = "progress"
    newCell.appendChild(progressIndicator)

    var req = new XMLHttpRequest()
    req.upload.addEventListener('load', () => { window.location = '?reverse' })
    req.upload.addEventListener('progress', (e) => {
      progressIndicator.style.width = e.loaded / e.total * 100 + '%'
    })
    req.open('POST', '/upload?filename=' + encodeURIComponent(file.name), true)
    req.send(file)
  }

  // Publish a document to the selected user group.

  const publish = async (hash, user_group) => {
    const response = await fetch(`/publish/${hash}/${user_group}`, { 'method': 'POST' })
    console.log(response)
    window.location.reload()
  }

  // Recall a document from the selected user group.

  const recall = async (hash, user_group) => {
    const response = await fetch(`/recall/${hash}/${user_group}`, { 'method': 'POST' })
    console.log(response)
    window.location.reload()
  }

  const _delete = async (hash) => {
    const response = await fetch(`/delete/${hash}`, { 'method': 'POST' })
    console.log(response)
    window.location.reload()
  }


  const handleButtons = function (e) {
    const d = e.target.dataset

    if (e.target.tagName == "TD") {
      if (e.target.classList.contains("published")) {
        console.log('recall', d.hash, d.userGroup)
        console.log(recall(d.hash, d.userGroup))
      } else if (e.target.classList.contains("delete")) {
        console.log('delete', d.hash)
        console.log(_delete(d.hash))
      } else {
        console.log('publish', d.hash, d.userGroup)
        console.log(publish(d.hash, d.userGroup))
      }
    }

    if (e.target.tagName == "BUTTON") {

      if (d.arg == "custom") {
        e.target.parentNode.className = 'identifier edit'

      } else if (e.target.className == "assign") {
        var req = new XMLHttpRequest()
        req.open('POST', `/identify/${d.hash}/${d.arg}`, true)
        req.addEventListener('load', () => { window.location.reload() })
        req.send()

      } else if (e.target.className == "delete") {
        var req = new XMLHttpRequest()
        req.open('POST', `/delete/${d.hash}`, true)
        req.addEventListener('load', () => { window.location.reload() })
        req.send()

      } else {
        console.log(d.hash, e.target.className, d.arg)
      }
    }
  }

  document.addEventListener('dragenter', highlight, false)
  document.addEventListener('dragleave', unhighlight, false)
  document.addEventListener('dragover', highlight, false)
  document.addEventListener('drop', accept, false)

  const maybeAttach = (_id, _event, callback) => {
    if (document.getElementById(_id) !== null) {
      document.getElementById(_id).addEventListener(_event, callback, false)
    }
  }

  maybeAttach('documents', 'click', handleButtons)

  if (document.getElementById('submenu')) {
    document.getElementById('submenu').addEventListener('click', (e) => {
      console.log(e)
    })
  }

})

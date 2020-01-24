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

  const handleMatrix = async function (e) {
    // don't do anything if the handler is fired by something other than a <td>
    if (e.target.tagName != "TD") return
    // figure out if we are on the settings page or the documents page
    const pageType = document.body.classList
    const d = e.target.dataset
    const url = "/" + pageType + "/" + d.action + "/" + d.row + "/" + (d.col || "")
    console.log(url)
    const response = await fetch(url, { 'method': 'POST' })
    console.log(response.status, response.body)
    //window.location.reload()
  }

  document.addEventListener('dragenter', highlight, false)
  document.addEventListener('dragleave', unhighlight, false)
  document.addEventListener('dragover', highlight, false)
  document.addEventListener('drop', accept, false)

  // Attach click handlers to the specified IDs, if they exist, without
  // throwing an error. This way, the same JavaScript can be run on every page.
  const maybeAttach = (_id, _event, callback) => {
    if (document.getElementById(_id) !== null) {
      document.getElementById(_id).addEventListener(_event, callback, false)
    }
  }

  maybeAttach('documents', 'click', handleMatrix)
  maybeAttach('users', 'click', handleMatrix)

  // Not sure what this does. Does it need to be removed?
  if (document.getElementById('submenu')) {
    document.getElementById('submenu').addEventListener('click', (e) => {
      console.log(e)
    })
  }

})

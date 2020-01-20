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

  const publish = async (hash, user_class) => {
    const response = await fetch(`/publish/${hash}/${user_class}`, { 'method': 'POST' })
    console.log(response)
    window.location.reload()
  }

  // Recall a document from the selected user group.

  const recall = async (hash, user_class) => {
    const response = await fetch(`/recall/${hash}/${user_class}`, { 'method': 'POST' })
    console.log(response)
    window.location.reload()
  }

  const _delete = async (hash) => {
    const response = await fetch(`/delete/${hash}`, { 'method': 'POST' })
    window.location.reload()
  }

  const grantSftp = async (name) => {
    const response = await fetch(`/settings/sftp/grant/${name}`, { 'method': 'POST' })
    console.log(response)
    // window.location.reload()
  }

  const denySftp = async (name) => {
    const response = await fetch(`/settings/sftp/grant/${name}`, { 'method': 'POST' })
    console.log(response)
    // window.location.reload()
  }

  const handleMatrix = function (e) {
    // don't do anything if the handler is fired by something other than a <td>
    if (e.target.tagName != "TD") return
    // figure out if we are on the settings page or the documents page
    const pageType = e.target.parentNode.parentNode.parentNode.id
    const d = e.target.dataset
    console.log(d.action, d.row, d.col)
    switch (d.action) {
      case 'delete':
        //_delete(d.idValue)
        break
      case 'publish':
        if (e.target.classList.contains('active'))
          recall(d.idValue, d.userClass)
        else
          publish(d.idValue, d.userClass)
        break
      case 'grant':
        if (e.target.classList.contains('active'))
          denySftp(d.idValue, d.userClass)
        else
          grantSftp(d.idValue, d.userClass)
        break
      default:
        console.error(d.action, 'not implemented')
    }
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
  maybeAttach('settings', 'click', handleMatrix)

  // Not sure what this does. Does it need to be removed?
  if (document.getElementById('submenu')) {
    document.getElementById('submenu').addEventListener('click', (e) => {
      console.log(e)
    })
  }

})

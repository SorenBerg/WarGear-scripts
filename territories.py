from PIL import Image
from hordify import WGMap
import sys
import random
from itertools import combinations
import time

MIN_TER_SIZE = 5
NEW_OPACITY = 99
BORDER_RADIUS = 5

class WGImage(WGMap):
    """A class designed to work with a WarGear map image.
       It takes an image for the board and an XML file representing the settings.
       Operations include creating territories, adding borders between nearby territories,
       and adding bonuses based on the border graph."""

#-------------------------------------------------------------------------------
#                              INIT FUNCTIONS
#-------------------------------------------------------------------------------

    def __init__(self):
        WGMap.__init__(self)
        self.img = None
        self.pix = None
        self.maxTerritoryId = 0
        self.territoryMap = {}
        self.min_ter_size = MIN_TER_SIZE

    def loadImageFromFile(self, filename):
        """Load an image into a buffer.
        Note: no changes will be made to the file even if the buffer is modified.
        Use saveImageToFile to persist changes."""
        self.img = Image.open(filename)
        self.pix = self.img.load()

    def saveImageToFile(self, filename):
        """Save the buffer to a file."""
        self.img.save(filename)

    def loadMapFromFile(self, filePath):
        """FIXME: This should be removed after refactoring."""
        WGMap.loadMapFromFile(self, filePath)
        
#------------------------------------------------------------------------------
#                         TERRITORIES
#------------------------------------------------------------------------------

    def makeTerritories(self, prefix, colorOnly=False):
        """Generate territories in the XML based on areas of contiguous color in the image."""
        max_x, max_y = self.img.size
        colors = self.getColorGenerator()
        names = self.getNameGenerator(prefix)
        self.setMaxTerritory()

        for i in range (0,max_x):
            for j in range(0,max_y):
                point = (i,j)
                if self.isColor(point):
                    newColor = colors.next()
                    center = self.floodFill(point, newColor)
                    if center == (0,0) or colorOnly:
                        continue
                    tid = self.addTerritory(names.next(), center[0], center[1])
                    self.territoryMap[newColor] = tid

        self.saveImageToFile('testout.png')

    def addTerritory(self, territoryName, xpos, ypos):
        """Add a territory to the XML."""
        boardID = self.DOM.getElementsByTagName("board")[0].getAttribute("boardid")
        self.maxTerritoryId += 1
        tid = str(self.maxTerritoryId)

        t = self.DOM.createElement("territory")
        t.setAttribute("boardid", boardID)
        t.setAttribute("name", territoryName)
        t.setAttribute("tid", tid)
        t.setAttribute("xpos", str(xpos))
        t.setAttribute("ypos", str(ypos))

        territories = self.DOM.getElementsByTagName("territories")[0]
        territories.appendChild(t)
        return tid

    def getTerritoryElementByTid(self, tid):
        for territory in self.DOM.getElementsByTagName("territory"):
            if territory.getAttribute("tid") == tid:
                return territory
        return None

    def getTerritoryElementByName(self, name):
        for territory in self.DOM.getElementsByTagName("territory"):
            if territory.getAttribute("name") == name:
                return territory
        return None

#------------------------------------------------------------------------------
#                         BORDERS
#------------------------------------------------------------------------------

    def makeBorders(self, radius, orthogonalOnly=False, attack='0', defend='0'):
        """Automatically adds borders for every pair of territories within x pixels of eachother.
           Requires each territory have a unique color.  Generally run after makeTerritories."""
        #build territoryMap if it wasn't created by makeTerritories
        if len(self.territoryMap) == 0:
            for territory in self.DOM.getElementsByTagName("territory"):
                point = (territory.getAttribute('xpos'),
                         territory.getAttribute('ypos'))
                color = self.getColorAtPoint(point)
                self.territoryMap[color] = territory.getAttribute('tid')

        borders = []
        max_x, max_y = self.img.size
        for i in range (0,max_x):
            for j in range(0,max_y):
                territories = self.findNearbyTerritories((i,j), radius, orthogonalOnly)
                for newBorder in combinations(territories, 2):
                    if newBorder[0] == newBorder[1] or newBorder in borders:
                        continue
                    self.addBorder(newBorder[0], newBorder[1], attack, defend)
                    borders.append(newBorder)

    def makeSquareBorders(self, radius, attack='0', defend='0'):
        for territory in self.DOM.getElementsByTagName("territory"):
            point = (int(territory.getAttribute('xpos')),
                     int(territory.getAttribute('ypos')))
            borders = []
            
            points = [(point[0] + radius, point[1]),
                      (point[0] - radius, point[1]),
                      (point[0], point[1] + radius),
                      (point[0], point[1] - radius)]
            for i in points:
                color = self.getColorAtPoint(i)
                try:
                    territory2 = self.territoryMap[color]
                except KeyError:
                    pass
                newBorder = [territory.getAttribute('tid'), territory2]
                newBorder.sort()
                tempt = self.getTerritoryElementByTid(territory2)
                
                if newBorder[0] == newBorder[1] or newBorder in borders:
                    continue
                self.addBorder(newBorder[0], newBorder[1], attack, defend)
                borders.append(newBorder)

    def addBorder(self, tid1, tid2, type_='Default', direction='Two-way', attack='0', defend='0'):
        """Add a border to the XML.
           TODO: the different types should be in an enum of some kind in case they change."""
        boardID = self.DOM.getElementsByTagName("board")[0].getAttribute("boardid")
        attack = str(attack)
        defend = str(defend)

        b = self.DOM.createElement("border")
        b.setAttribute('boardid', boardID)
        b.setAttribute('fromid', str(tid1))
        b.setAttribute('toid', str(tid2))
        b.setAttribute('direction', direction)
        b.setAttribute('type', type_)
        if direction == 'Two-way':
            b.setAttribute('ftattackmod', attack)
            b.setAttribute('ftdefendmod', defend)
            b.setAttribute('tfattackmod', attack)
            b.setAttribute('tfdefendmod', defend)
        else:
            b.setAttribute('ftattackmod', attack)
            b.setAttribute('ftdefendmod', defend)

        borders = self.DOM.getElementsByTagName("borders")[0]
        borders.appendChild(b)
                    
    def borderAll(self, name, deleteExisting=True, direction='both', type_='Default', attack='0', defend='0'):
        """Make a single territory border all others."""
        target = None
        territoryList = []
        for territory in self.DOM.getElementsByTagName("territory"):
            if territory.getAttribute('name') == name:
                target = territory.getAttribute('tid')
            else:
                territoryList.append(territory.getAttribute('tid'))

        if not target:
            print 'no target found'
            return

        borders = self.DOM.getElementsByTagName("borders")[0]
        if deleteExisting:
            for border in self.DOM.getElementsByTagName("border"):
                if (border.getAttribute('fromid') == target or
                    border.getAttribute('toid') == target):
                    borders.removeChild(border)

        for tid in territoryList:
            if direction == 'both':
                self.addBorder(target, tid, type_, 'Two-way', attack, defend)
            elif direction == 'from':
                self.addBorder(target, tid, type_, 'One-way', attack, defend)
            elif direction == 'to':
                self.addBorder(tid, target, type_, 'One-way', attack, defend)
            else:
                print 'invalid direction for borderAll'
                                 
#------------------------------------------------------------------------------
#                         CONTINENTS
#------------------------------------------------------------------------------
    def xConnectedContinents(self, depth, bonus=1):
        """Add a continent for any group of territories of size x that are connected."""
        queue = []
        continents = set()
        for territory in self.DOM.getElementsByTagName("territory"):

            # start with a single territory
            queue.append({'territory': territory,
                          'depth': 1,
                          'path': [territory,]})
            while queue:
                curNode = queue.pop()
                # if at the right depth save the path
                if curNode['depth'] == depth:
                    group = [x.getAttribute('tid') for x in curNode['path']]
                    group.sort()
                    continents.add(','.join(group))
                    continue
                # if not at the right depth add children to queue
                for node in self.findNeighbors(curNode['territory']):
                    # avoid loops
                    if node in curNode['path'] or node == None:
                        continue
                    newPath = curNode['path'] + [node,]
                    nextNode = {'territory': node,
                                'depth': curNode['depth'] + 1,
                                'path': newPath}
                    queue.append(nextNode)

            # If the queue is empty or list is complete and we can add it as
            # a continent
        for continent in continents:
            self.addContinent(continent, continent, bonus=bonus, fromString=True)

    def noSplitContinents(self, num, bonus=1):
        """Add a continent for any group of territories that connect in a chain."""
        queue = []
        continents = set()
        for territory in self.DOM.getElementsByTagName("territory"):
            neighbors = set(self.findNeighbors(territory))
            for group in combinations(neighbors, num):
                ### add territory to the end to make sets of num
                group = list(group)
                group.append(territory)
                tidgroup = [x.getAttribute('tid') for x in group]
                tidgroup.sort()
                continents.add(','.join(tidgroup))

        for continent in continents:
            self.addContinent(continent, continent, bonus=bonus, fromString=True)


    def interconnectedContinents(self, bonus=1):
        """Add a continent for any group of x territories where each teritory is
           connected to evey other territory in the set."""
        queue = []
        continents = set()
        for territory in self.DOM.getElementsByTagName("territory"):
            neighbors = set(self.findNeighbors(territory))
            for neighbor in neighbors:
                relatives = set(self.findNeighbors(neighbor))
                ### for each neighbor get all relatives that border the original
                for relative in neighbors.intersection(relatives):
                    group = [relative, neighbor, territory]
                    tidgroup = [x.getAttribute('tid') for x in group]
                    tidgroup.sort()
                    continents.add(','.join(tidgroup))

        print len(continents)
        for continent in continents:
            self.addContinent(continent, continent, bonus=bonus, fromString=True)

#------------------------------------------------------------------------------
#                         HELPER FUNCTIONS
#------------------------------------------------------------------------------

    def isColor(self, point):
        try:
            return self.pix[point][3] > 200
        except:
            return False

    def floodFill(self, point, newColor=(0,0,0,0)):
        """Perform a flood fill from a point and return the center of it's bounding box.
           newColor will replace whatever color was there previously."""
        queue = []
        max_x = 0
        max_y = 0
        min_x,min_y = point
        queue.append(point)
        while queue:
            point = queue.pop()
            if self.isColor(point):
                # set alpha
                self.pix[point] = newColor
                # check min/max boundries
                min_x = min(point[0], min_x)
                min_y = min(point[1], min_y)
                max_x = max(point[0], max_x)
                max_y = max(point[1], max_y)
                # test all neighbors
                queue.append((point[0], point[1] + 1))
                queue.append((point[0], point[1] - 1))
                queue.append((point[0] + 1, point[1]))
                queue.append((point[0] - 1, point[1]))

        # draw bounding box
    #    for i in range(min_x, max_x):
    #        pix[i,max_y] = color
    #        pix[i,min_y] = color
    #    for i in range(min_y, max_y):
    #        pix[max_x,i] = color
    #        pix[min_x,i] = color

        # find center of bounding box
        xdelta = max_x - min_x
        ydelta = max_y - min_y
        if xdelta > self.min_ter_size and ydelta > self.min_ter_size:
            x = xdelta/2 + min_x
            y = ydelta/2 + min_y
            return (x,y)
        else:
            return (0,0)

    def findNearbyTerritories(self, point, radius, orthogonalOnly=False):
        """FIXME: does not actually look in a circle because I don't like trig.
           Finds all the territories within radius pixels of a given point."""
        results = []
        dradius = radius - 1
        points = [point,
                  (point[0] + radius, point[1]),
                  (point[0] - radius, point[1]),
                  (point[0], point[1] + radius),
                  (point[0], point[1] - radius)]
        if not orthogonalOnly:
            points.extend([(point[0] + dradius, point[1] + dradius),
                           (point[0] + dradius, point[1] - dradius),
                           (point[0] - dradius, point[1] + dradius),
                           (point[0] - dradius, point[1] - dradius)])
        for i in points:
            color = self.getColorAtPoint(i)
            try:
                results.append(self.territoryMap[color])
            except KeyError:
                pass
        return results

    def getTerritoryAtPoint(self, point):
        color = self.getColorAtPoint(point)
        try:
            self.getTerritoryElementByTid(self.territoryMap[color])
        except KeyError:
            return False

    def setMaxTerritory(self):
        """Find the territory with the highest id and set as a class variable."""
        self.maxTerritoryId = 0
        for territory in self.DOM.getElementsByTagName("territory"):
            self.maxTerritoryId = max(self.maxTerritoryId,
                                      int(territory.getAttribute("tid")))

    def getColorGenerator(self):
        """Yeild successive unique colors for use as territory identifiers.
           New opacity should be set to anything other than the current opacity
           of the image."""
        for r in range(0,255):
            for g in range(0,255):
                for b in range(0,255):
                    yield (r,g,b,NEW_OPACITY)

    def getNameGenerator(self, prefix):
        """Generate names for new territories."""
        for i in range(0,10000):
            yield '%s%s' % (prefix, i)

    def getColorAtPoint(self, point):
        """Lookup the value of a pixel at point."""
        try:
            return self.pix[point]
        except:
            return None
    
    def randomColor():
        return (random.randint(0,255),random.randint(0,255),random.randint(0,255),199)

#------------------------------------------------------------------------------
#                         REMOVAL
#------------------------------------------------------------------------------

    def clearBorders(self):
        """Remove all borders from XML."""
        borders = self.DOM.getElementsByTagName("borders")[0]
        for border in self.DOM.getElementsByTagName("border"):
            borders.removeChild(border)
    
    def removeDiagonalBorders(self):
        """Remove diagonal borders from XML."""
        borders = self.DOM.getElementsByTagName("borders")[0]
        for border in self.DOM.getElementsByTagName("border"):
            fromid = border.getAttribute('fromid')
            toid = border.getAttribute('toid')
            
            t1 = self.getTerritoryElementByTid(fromid)
            t2 = self.getTerritoryElementByTid(toid)
            
            if (abs(int(t1.getAttribute('xpos')) - int(t2.getAttribute('xpos'))) > 10 and
                abs(int(t1.getAttribute('ypos')) - int(t2.getAttribute('ypos'))) > 10):
                borders.removeChild(border)

    def clearContinents(self):
        """Remove all continents from XML."""
        continents = self.DOM.getElementsByTagName("continents")[0]
        for continent in self.DOM.getElementsByTagName("continent"):
            continents.removeChild(continent)

    def clearMap(self):
        """Remove all territories, borders, and continents from XML."""
        self.clearTerritories()
        self.clearBorders()
        self.clearContinents()
        
    def clearTerritories(self):
        """Remove all territories from XML."""
        territories = self.DOM.getElementsByTagName("territories")[0]
        for territory in self.DOM.getElementsByTagName("territory"):
            territories.removeChild(territory)

#------------------------------------------------------------------------------
#                         MAIN
#------------------------------------------------------------------------------

if __name__ == "__main__":
    """An example script.  Usage: python territories.py XML image prefix"""

    argslist = sys.argv[1:]

    if len(argslist) != 3:
        print "usage: python territories.py XML image prefix"
        exit(0)

    XML,image,prefix = argslist
    t1 = time.time()
    wgimage = WGImage()
    wgimage.loadMapFromFile(XML)
    wgimage.loadImageFromFile(image)

    print 'clear territories and borders and continents'
    print str(time.time() - t1)
    print wgimage.maxTerritoryId
    wgimage.clearMap()
    print 'make territories'
    print str(time.time() - t1)
    wgimage.makeTerritories(prefix)
    print wgimage.maxTerritoryId

    print 'make borders'
    print str(time.time() - t1)
    wgimage.makeBorders(6)

    print 'X connected'
    print str(time.time() - t1)
    wgimage.interconnectedContinents(bonus=-8)
    wgimage.xConnectedContinents(2, bonus=1)


    wgimage.saveMapToFile('Wall of Thorns2.xml')
